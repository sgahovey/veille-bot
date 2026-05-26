"""Appel à l'API Gemini pour classer et résumer les articles.

Stratégie : un seul appel batch par exécution, JSON forcé via
``response_mime_type``. Retry exponentiel sur erreur réseau, fallback
gracieux si le parsing JSON échoue après les retries.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from src.domain.models import Article, ArticleAnalyse, Digest, WeeklyRecap

logger = logging.getLogger(__name__)

DOSSIER_PROMPTS = Path(__file__).resolve().parent.parent.parent / "prompts"
CHEMIN_PROMPT = DOSSIER_PROMPTS / "digest_prompt.md"
CHEMIN_PROMPT_RECAP = DOSSIER_PROMPTS / "weekly_recap_prompt.md"

CRITICITES_AUTORISEES = {"critique", "important", "interessant", "ignore"}
CATEGORIES_AUTORISEES = {"securite", "backend", "frontend", "devops", "ia", "general"}
MAX_TOP_PRIORITES = 3
MAX_RETRY = 3
BACKOFF_BASE_SECONDES = 2


class GeminiRepository:
    """Wrapper haut niveau autour du SDK google-genai."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        """Initialise le client Gemini.

        Args:
            api_key: Clé API Google AI Studio.
            model: Identifiant du modèle (défaut: gemini-2.5-flash).
        """
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._prompt_template = CHEMIN_PROMPT.read_text(encoding="utf-8")
        self._prompt_recap_template = CHEMIN_PROMPT_RECAP.read_text(encoding="utf-8")

    def generer_digest(self, articles: list[Article]) -> Digest:
        """Génère un Digest à partir d'articles via Gemini.

        Args:
            articles: Articles à soumettre à l'IA.

        Returns:
            Un ``Digest`` complet — soit issu de l'analyse IA, soit un
            digest minimal de repli si l'IA est indisponible.
        """
        if not articles:
            return Digest(
                date_generation=datetime.now(timezone.utc),
                nb_articles_analyses=0,
                nb_articles_retenus=0,
                synthese_journee="Aucun article à analyser aujourd'hui.",
            )

        prompt = self._construire_prompt(articles)
        reponse_json = self._appeler_avec_retry(prompt)

        if reponse_json is None:
            logger.warning("gemini_fallback_active")
            return self._digest_fallback(articles)

        try:
            return self._mapper_vers_digest(reponse_json, articles)
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(
                "gemini_mapping_echec",
                extra={"contexte": {"erreur": str(exc)}},
            )
            return self._digest_fallback(articles)

    def _construire_prompt(self, articles: list[Article]) -> str:
        """Sérialise les articles en JSON minimal et l'injecte dans le template."""
        articles_json = json.dumps(
            [
                {
                    "hash_unique": a.hash_unique,
                    "titre": a.titre,
                    "resume": a.resume,
                    "source": a.source,
                    "categorie_source": a.categorie_source,
                }
                for a in articles
            ],
            ensure_ascii=False,
        )
        return self._prompt_template.replace("{articles_json}", articles_json)

    def _appeler_avec_retry(self, prompt: str) -> dict[str, Any] | None:
        """Appelle Gemini avec retry exponentiel. Retourne None si tout échoue."""
        config = types.GenerateContentConfig(response_mime_type="application/json")

        for tentative in range(1, MAX_RETRY + 1):
            try:
                reponse = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                texte = (getattr(reponse, "text", "") or "").strip()
                if not texte:
                    raise ValueError("réponse vide")
                return json.loads(texte)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "gemini_parse_echec",
                    extra={"contexte": {"tentative": tentative, "erreur": str(exc)}},
                )
            except Exception as exc:  # noqa: BLE001 — réseau, quota, etc.
                logger.warning(
                    "gemini_appel_echec",
                    extra={"contexte": {"tentative": tentative, "erreur": str(exc)}},
                )

            if tentative < MAX_RETRY:
                time.sleep(BACKOFF_BASE_SECONDES * (2 ** (tentative - 1)))

        return None

    def _mapper_vers_digest(
        self, reponse: dict[str, Any], articles: list[Article]
    ) -> Digest:
        """Convertit la réponse JSON Gemini en Digest typé."""
        index_par_hash = {a.hash_unique: a for a in articles}
        analyses_brutes = reponse.get("articles_analyses", [])
        tldr = str(reponse.get("tldr", "")).strip()
        synthese = str(reponse.get("synthese_journee", "")).strip()

        analyses: list[ArticleAnalyse] = []
        for brut in analyses_brutes:
            hash_unique = str(brut.get("hash_unique", ""))
            article = index_par_hash.get(hash_unique)
            if article is None:
                continue
            criticite = str(brut.get("criticite", "ignore"))
            if criticite not in CRITICITES_AUTORISEES:
                criticite = "ignore"
            categorie = str(brut.get("categorie", "general"))
            if categorie not in CATEGORIES_AUTORISEES:
                categorie = "general"
            score = brut.get("score", 1)
            try:
                score_int = max(1, min(10, int(score)))
            except (TypeError, ValueError):
                score_int = 1
            analyses.append(
                ArticleAnalyse(
                    article=article,
                    garde=bool(brut.get("garde", False)),
                    criticite=criticite,
                    score=score_int,
                    raison_courte=str(brut.get("raison_courte", "")).strip(),
                    categorie=categorie,
                    titre_traduit=str(brut.get("titre_traduit", "")).strip(),
                )
            )

        retenus = [a for a in analyses if a.garde]
        retenus.sort(key=_cle_tri_analyse)

        top: list[ArticleAnalyse] = []
        autres: list[ArticleAnalyse] = []
        for analyse in retenus:
            if analyse.criticite in {"critique", "important"} and len(top) < MAX_TOP_PRIORITES:
                top.append(analyse)
            else:
                autres.append(analyse)

        return Digest(
            date_generation=datetime.now(timezone.utc),
            nb_articles_analyses=len(articles),
            nb_articles_retenus=len(retenus),
            top_priorites=top,
            autres_articles=autres,
            tldr=tldr,
            synthese_journee=synthese or "Synthèse indisponible.",
        )

    def generer_recap_hebdo(
        self,
        analyses: list[ArticleAnalyse],
        date_debut: datetime,
        date_fin: datetime,
        semaine_iso: str,
    ) -> WeeklyRecap:
        """Génère un ``WeeklyRecap`` à partir des analyses retenues sur la semaine.

        Args:
            analyses: Articles avec ``garde=True`` de la semaine écoulée.
            date_debut: Lundi 00:00 UTC.
            date_fin: Dimanche 23:59 UTC.
            semaine_iso: Identifiant ISO (ex: ``"2026-W21"``).

        Returns:
            Un ``WeeklyRecap`` complet — soit issu de l'IA, soit un fallback
            minimal si l'IA est indisponible.
        """
        par_categorie = _grouper_par_categorie(analyses)

        if not analyses:
            return WeeklyRecap(
                semaine_iso=semaine_iso,
                date_debut=date_debut,
                date_fin=date_fin,
                nb_articles_total=0,
                par_categorie=par_categorie,
                tendances="Aucun article retenu cette semaine.",
                date_generation=datetime.now(timezone.utc),
            )

        prompt = self._construire_prompt_recap(analyses, date_debut, date_fin)
        reponse_json = self._appeler_avec_retry(prompt)

        if reponse_json is None:
            logger.warning("gemini_recap_fallback_active")
            return self._recap_fallback(analyses, date_debut, date_fin, semaine_iso)

        try:
            return self._mapper_vers_recap(
                reponse_json, analyses, date_debut, date_fin, semaine_iso
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.error(
                "gemini_recap_mapping_echec",
                extra={"contexte": {"erreur": str(exc)}},
            )
            return self._recap_fallback(analyses, date_debut, date_fin, semaine_iso)

    def _construire_prompt_recap(
        self,
        analyses: list[ArticleAnalyse],
        date_debut: datetime,
        date_fin: datetime,
    ) -> str:
        """Sérialise les analyses et injecte dates + JSON dans le template."""
        articles_json = json.dumps(
            [
                {
                    "hash_unique": a.article.hash_unique,
                    "titre": a.titre_traduit or a.article.titre,
                    "resume": a.article.resume,
                    "source": a.article.source,
                    "criticite": a.criticite,
                    "categorie": a.categorie,
                    "score": a.score,
                    "raison_courte": a.raison_courte,
                }
                for a in analyses
            ],
            ensure_ascii=False,
        )
        prompt = self._prompt_recap_template
        prompt = prompt.replace("{articles_json}", articles_json)
        prompt = prompt.replace("{date_debut}", date_debut.strftime("%d/%m/%Y"))
        prompt = prompt.replace("{date_fin}", date_fin.strftime("%d/%m/%Y"))
        return prompt

    def _mapper_vers_recap(
        self,
        reponse: dict[str, Any],
        analyses: list[ArticleAnalyse],
        date_debut: datetime,
        date_fin: datetime,
        semaine_iso: str,
    ) -> WeeklyRecap:
        """Construit un ``WeeklyRecap`` à partir de la réponse Gemini."""
        tendances = str(reponse.get("tendances", "")).strip()
        top_3_hashes = list(reponse.get("top_3_hashes", []))[:3]
        a_retenir_brut = list(reponse.get("a_retenir", []))[:3]
        a_retenir = [str(item).strip() for item in a_retenir_brut if str(item).strip()]

        index_par_hash = {a.article.hash_unique: a for a in analyses}
        top_3 = [
            index_par_hash[h]
            for h in top_3_hashes
            if h in index_par_hash
        ]

        return WeeklyRecap(
            semaine_iso=semaine_iso,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_articles_total=len(analyses),
            top_3=top_3,
            par_categorie=_grouper_par_categorie(analyses),
            tendances=tendances or "Synthèse hebdomadaire indisponible.",
            a_retenir=a_retenir,
            date_generation=datetime.now(timezone.utc),
        )

    def _recap_fallback(
        self,
        analyses: list[ArticleAnalyse],
        date_debut: datetime,
        date_fin: datetime,
        semaine_iso: str,
    ) -> WeeklyRecap:
        """Récap minimal si l'IA est indisponible — top 3 par score brut."""
        tries = sorted(analyses, key=_cle_tri_analyse)
        return WeeklyRecap(
            semaine_iso=semaine_iso,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_articles_total=len(analyses),
            top_3=tries[:3],
            par_categorie=_grouper_par_categorie(analyses),
            tendances=(
                "Synthèse IA indisponible cette semaine. Top 3 calculé par "
                "tri sur criticité puis score."
            ),
            a_retenir=[],
            date_generation=datetime.now(timezone.utc),
        )

    def _digest_fallback(self, articles: list[Article]) -> Digest:
        """Digest minimal si l'IA est indisponible : tout en ``interessant``."""
        analyses = [
            ArticleAnalyse(
                article=a,
                garde=True,
                criticite="interessant",
                score=5,
                raison_courte="Classement IA indisponible — article brut.",
                categorie=a.categorie_source,
            )
            for a in articles[:8]
        ]
        return Digest(
            date_generation=datetime.now(timezone.utc),
            nb_articles_analyses=len(articles),
            nb_articles_retenus=len(analyses),
            top_priorites=[],
            autres_articles=analyses,
            synthese_journee=(
                "Le classement automatique n'a pas pu être généré ; "
                "voici les articles bruts du jour."
            ),
        )


def _cle_tri_analyse(analyse: ArticleAnalyse) -> tuple[int, int]:
    """Clé de tri : criticité décroissante puis score décroissant."""
    ordre = {"critique": 0, "important": 1, "interessant": 2, "ignore": 3}
    return (ordre.get(analyse.criticite, 3), -analyse.score)


def _grouper_par_categorie(
    analyses: list[ArticleAnalyse],
) -> dict[str, list[ArticleAnalyse]]:
    """Regroupe les analyses par catégorie, trie chaque groupe par criticité/score."""
    groupes: dict[str, list[ArticleAnalyse]] = {}
    for analyse in analyses:
        groupes.setdefault(analyse.categorie, []).append(analyse)
    for cat in groupes:
        groupes[cat].sort(key=_cle_tri_analyse)
    return groupes
