"""Export du WeeklyRecap au format Markdown — pour archive sur le repo."""

from __future__ import annotations

import logging
from pathlib import Path

from src.domain.models import ArticleAnalyse, WeeklyRecap

logger = logging.getLogger(__name__)

EMOJI_CRITICITE = {
    "critique": "🚨",
    "important": "⚠️",
    "interessant": "💡",
    "ignore": "⏭️",
}

EMOJI_CATEGORIE = {
    "securite": "🔐",
    "backend": "⚙️",
    "frontend": "🎨",
    "devops": "🚀",
    "ia": "🤖",
    "general": "📚",
}

LIBELLE_CATEGORIE = {
    "securite": "Sécurité",
    "backend": "Backend",
    "frontend": "Frontend",
    "devops": "DevOps",
    "ia": "IA",
    "general": "Général",
}

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


class MarkdownExporter:
    """Convertit un ``WeeklyRecap`` en fichier Markdown ``YYYY-Wnn.md``."""

    def exporter_recap(self, recap: WeeklyRecap, output_dir: Path) -> Path:
        """Génère le fichier Markdown et retourne son chemin.

        Args:
            recap: Récap à exporter.
            output_dir: Dossier de sortie (créé s'il n'existe pas).

        Returns:
            Chemin du fichier écrit.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        fichier = output_dir / f"{recap.semaine_iso}.md"
        contenu = self._construire_contenu(recap)
        fichier.write_text(contenu, encoding="utf-8")
        logger.info(
            "markdown_export_ok",
            extra={"contexte": {"fichier": str(fichier), "taille": len(contenu)}},
        )
        return fichier

    def _construire_contenu(self, recap: WeeklyRecap) -> str:
        """Compose le contenu Markdown complet du récap."""
        parties: list[str] = []
        parties.append(self._titre_principal(recap))
        parties.append(self._vue_ensemble(recap))
        parties.append(self._section_top_3(recap))
        parties.append(self._section_repartition(recap))
        parties.append(self._section_tendances(recap))
        parties.append(self._section_a_retenir(recap))
        parties.append(self._section_tous_articles(recap))
        return "\n\n".join(parties) + "\n"

    def _titre_principal(self, recap: WeeklyRecap) -> str:
        debut = _format_date_fr_court(recap.date_debut)
        fin = _format_date_fr_court(recap.date_fin)
        gen = _format_datetime_fr(recap.date_generation)
        numero_semaine = recap.semaine_iso.split("-W")[-1]
        return (
            f"# Récap veille — Semaine {numero_semaine} (du {debut} au {fin})\n\n"
            f"> Généré automatiquement le {gen}"
        )

    def _vue_ensemble(self, recap: WeeklyRecap) -> str:
        debut = _format_date_fr(recap.date_debut)
        fin = _format_date_fr(recap.date_fin)
        return (
            "## Vue d'ensemble\n\n"
            f"- **Articles retenus** : {recap.nb_articles_total}\n"
            f"- **Période** : {debut} → {fin}"
        )

    def _section_top_3(self, recap: WeeklyRecap) -> str:
        lignes = ["## Top 3 de la semaine"]
        if not recap.top_3:
            lignes.append("\n_Pas d'article phare cette semaine._")
            return "\n".join(lignes)
        for i, analyse in enumerate(recap.top_3, start=1):
            titre = analyse.titre_traduit or analyse.article.titre
            crit_emoji = EMOJI_CRITICITE.get(analyse.criticite, "•")
            cat_emoji = EMOJI_CATEGORIE.get(analyse.categorie, "📚")
            cat_label = LIBELLE_CATEGORIE.get(analyse.categorie, analyse.categorie)
            lignes.append(
                f"\n### {i}. [{titre}]({analyse.article.lien})\n\n"
                f"**Criticité** : {crit_emoji} {analyse.criticite}  \n"
                f"**Catégorie** : {cat_emoji} {cat_label}  \n"
                f"**Source** : {analyse.article.source}  \n"
                f"**Raison** : {analyse.raison_courte}"
            )
        return "\n".join(lignes)

    def _section_repartition(self, recap: WeeklyRecap) -> str:
        lignes = [
            "## Répartition par catégorie",
            "",
            "| Catégorie | Nombre |",
            "|-----------|--------|",
        ]
        for cat in ("securite", "backend", "frontend", "devops", "ia", "general"):
            nb = len(recap.par_categorie.get(cat, []))
            emoji = EMOJI_CATEGORIE.get(cat, "📚")
            label = LIBELLE_CATEGORIE.get(cat, cat.capitalize())
            lignes.append(f"| {emoji} {label} | {nb} |")
        return "\n".join(lignes)

    def _section_tendances(self, recap: WeeklyRecap) -> str:
        return (
            "## Tendances de la semaine\n\n"
            f"{recap.tendances or '_Aucune tendance identifiée._'}"
        )

    def _section_a_retenir(self, recap: WeeklyRecap) -> str:
        if not recap.a_retenir:
            return "## À retenir\n\n_Pas de takeaway cette semaine._"
        lignes = ["## À retenir", ""]
        for i, item in enumerate(recap.a_retenir, start=1):
            lignes.append(f"{i}. {item}")
        return "\n".join(lignes)

    def _section_tous_articles(self, recap: WeeklyRecap) -> str:
        lignes = ["## Tous les articles de la semaine"]
        ordre_categories = ("securite", "backend", "frontend", "devops", "ia", "general")
        for cat in ordre_categories:
            articles = recap.par_categorie.get(cat, [])
            if not articles:
                continue
            emoji = EMOJI_CATEGORIE.get(cat, "📚")
            label = LIBELLE_CATEGORIE.get(cat, cat.capitalize())
            lignes.append(f"\n### {emoji} {label}\n")
            for analyse in articles:
                lignes.append(_ligne_article(analyse))
        return "\n".join(lignes)


def _ligne_article(analyse: ArticleAnalyse) -> str:
    titre = analyse.titre_traduit or analyse.article.titre
    raison = analyse.raison_courte
    return f"- [{titre}]({analyse.article.lien}) — _{raison}_"


def _format_date_fr(dt) -> str:
    return f"{dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"


def _format_date_fr_court(dt) -> str:
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"


def _format_datetime_fr(dt) -> str:
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year} à {dt.hour:02d}:{dt.minute:02d}"
