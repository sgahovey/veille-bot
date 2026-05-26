"""Orchestrateur du récap hebdomadaire (workflow du dimanche soir).

Enchaîne : calcul des bornes de la semaine ISO → lecture SQLite des analyses
retenues → appel Gemini avec le prompt récap → export Markdown + publication
Discord multi-embeds.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from src.domain.analyse_repository import AnalyseRepository
from src.domain.models import WeeklyRecap
from src.domain.week_helpers import bornes_semaine_iso, libelle_semaine_iso
from src.infrastructure.discord_repository import DiscordRepository
from src.infrastructure.gemini_repository import GeminiRepository
from src.infrastructure.markdown_exporter import MarkdownExporter

logger = logging.getLogger(__name__)


class WeeklyRecapService:
    """Use case : produire le récap hebdomadaire et le publier."""

    def __init__(
        self,
        analyse_repo: AnalyseRepository,
        gemini_repo: GeminiRepository,
        discord_repo: DiscordRepository,
        markdown_exporter: MarkdownExporter,
        output_dir: Path,
        repo_github_url: str | None = None,
    ) -> None:
        """Injecte les dépendances et le dossier d'export Markdown.

        Args:
            analyse_repo: Source des analyses retenues sur la semaine.
            gemini_repo: Client Gemini pour générer le récap.
            discord_repo: Client Discord pour la publication multi-embeds.
            markdown_exporter: Génère le fichier Markdown archivé sur le repo.
            output_dir: Dossier où écrire le fichier ``YYYY-Wnn.md``.
            repo_github_url: URL publique du repo (ex: ``https://github.com/u/r``).
                Utilisée pour construire le lien direct vers le Markdown dans
                le dernier embed Discord.
        """
        self._analyse_repo = analyse_repo
        self._gemini_repo = gemini_repo
        self._discord_repo = discord_repo
        self._markdown_exporter = markdown_exporter
        self._output_dir = output_dir
        self._repo_github_url = repo_github_url

    def executer(self, maintenant: datetime | None = None) -> None:
        """Lance le pipeline complet du récap hebdomadaire.

        Args:
            maintenant: Date de référence (utile pour les tests). Par défaut,
                l'heure courante UTC.
        """
        ref = maintenant or datetime.now(timezone.utc)
        date_debut, date_fin = bornes_semaine_iso(ref)
        semaine = libelle_semaine_iso(ref)

        logger.info(
            "recap_execution_demarree",
            extra={
                "contexte": {
                    "semaine": semaine,
                    "debut": date_debut.isoformat(),
                    "fin": date_fin.isoformat(),
                }
            },
        )

        analyses = self._analyse_repo.lister_gardes_periode(date_debut, date_fin)
        logger.info(
            "recap_articles_charges",
            extra={"contexte": {"count": len(analyses)}},
        )

        if not analyses:
            logger.info("recap_rien_a_publier")
            return

        recap = self._gemini_repo.generer_recap_hebdo(
            analyses, date_debut, date_fin, semaine
        )

        fichier_md = self._markdown_exporter.exporter_recap(recap, self._output_dir)
        lien_md = self._construire_lien_markdown(fichier_md)

        publie = self._discord_repo.publier_recap_hebdo(recap, lien_markdown=lien_md)
        if publie:
            logger.info(
                "recap_execution_terminee",
                extra={
                    "contexte": {
                        "semaine": semaine,
                        "articles": recap.nb_articles_total,
                        "markdown": str(fichier_md),
                    }
                },
            )
        else:
            logger.error("recap_publication_discord_echec")

    def _construire_lien_markdown(self, fichier_md: Path) -> str | None:
        """Construit l'URL publique GitHub du fichier MD si possible."""
        if not self._repo_github_url:
            return None
        base = self._repo_github_url.rstrip("/")
        # docs/veille/YYYY-Wnn.md (chemin depuis la racine du repo)
        chemin_relatif = fichier_md.relative_to(self._output_dir.parent.parent)
        chemin_normalise = str(chemin_relatif).replace("\\", "/")
        return f"{base}/blob/main/{chemin_normalise}"
