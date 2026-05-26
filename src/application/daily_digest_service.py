"""Orchestrateur principal du bot de veille.

Enchaîne : lecture RSS parallèle → filtrage 24h → dédup → appel Gemini →
publication Discord → marquage des articles vus. Toute exception levée
dans une étape externe est convertie en log : aucune n'interrompt l'exécution
des étapes restantes lorsqu'une dégradation gracieuse est possible.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from src.domain.analyse_repository import AnalyseRepository
from src.domain.article_filter import filtrer_dernieres_24h
from src.domain.deduplicator import Deduplicator
from src.domain.models import Article
from src.infrastructure.discord_repository import DiscordRepository
from src.infrastructure.gemini_repository import GeminiRepository

logger = logging.getLogger(__name__)

MAX_WORKERS_RSS = 5


class DailyDigestService:
    """Use case principal : produire et publier le digest quotidien."""

    def __init__(
        self,
        sources: list[dict],
        rss_reader: Callable[[dict], list[Article]],
        deduplicator: Deduplicator,
        gemini_repo: GeminiRepository,
        discord_repo: DiscordRepository,
        analyse_repo: AnalyseRepository | None = None,
    ) -> None:
        """Injecte toutes les dépendances nécessaires.

        Args:
            sources: Liste des sources RSS (dicts avec ``nom``, ``url``, ``categorie``).
            rss_reader: Fonction qui transforme une source en liste d'articles.
            deduplicator: Filtre des articles déjà traités.
            gemini_repo: Client Gemini pour la génération du digest.
            discord_repo: Client Discord pour la publication.
            analyse_repo: Optionnel — si fourni, chaque analyse retenue est
                persistée pour alimenter le récap hebdomadaire.
        """
        self._sources = sources
        self._rss_reader = rss_reader
        self._deduplicator = deduplicator
        self._gemini_repo = gemini_repo
        self._discord_repo = discord_repo
        self._analyse_repo = analyse_repo

    def executer(self) -> None:
        """Lance le pipeline complet du digest quotidien."""
        logger.info("execution_demarree", extra={"contexte": {"sources": len(self._sources)}})

        articles_bruts = self._lire_flux_paralleles()
        logger.info(
            "rss_collecte_terminee",
            extra={"contexte": {"total": len(articles_bruts)}},
        )

        maintenant = datetime.now(timezone.utc)
        articles_recents = filtrer_dernieres_24h(articles_bruts, maintenant)
        logger.info(
            "filtrage_24h_termine",
            extra={"contexte": {"recents": len(articles_recents)}},
        )

        articles_nouveaux = self._deduplicator.filtrer_nouveaux(articles_recents)
        if not articles_nouveaux:
            logger.info("rien_a_publier")
            return

        digest = self._gemini_repo.generer_digest(articles_nouveaux)

        publie = self._discord_repo.publier_digest(digest)
        if publie:
            self._deduplicator.marquer_traites(articles_nouveaux)
            if self._analyse_repo is not None:
                analyses_retenues = digest.top_priorites + digest.autres_articles
                for analyse in analyses_retenues:
                    self._analyse_repo.enregistrer_analyse(analyse)
                logger.info(
                    "analyses_persistees",
                    extra={"contexte": {"count": len(analyses_retenues)}},
                )
            logger.info(
                "execution_terminee",
                extra={
                    "contexte": {
                        "analyses": digest.nb_articles_analyses,
                        "retenus": digest.nb_articles_retenus,
                        "marques_vus": len(articles_nouveaux),
                    }
                },
            )
        else:
            logger.error("publication_discord_echec_pas_de_marquage")

    def _lire_flux_paralleles(self) -> list[Article]:
        """Lit toutes les sources RSS en parallèle (max 5 workers)."""
        articles: list[Article] = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS_RSS) as executor:
            futurs = {executor.submit(self._rss_reader, src): src for src in self._sources}
            for futur in as_completed(futurs):
                source = futurs[futur]
                try:
                    articles.extend(futur.result())
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "rss_futur_echec",
                        extra={
                            "contexte": {
                                "source": source.get("nom", "?"),
                                "erreur": str(exc),
                            }
                        },
                    )
        return articles
