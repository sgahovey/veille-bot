"""Publication du Digest sur Discord via webhook.

Construit un embed riche en respectant les limites de l'API Discord :
title ≤ 256, field.value ≤ 1024, embed total ≤ 6000 caractères, ≤ 25 fields.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from src.domain.models import ArticleAnalyse, Digest

logger = logging.getLogger(__name__)

COULEUR_BLEU = 0x3498DB
TIMEOUT_HTTP = 10
LIMITE_TITLE = 256
LIMITE_FIELD_VALUE = 1024
LIMITE_TOTAL_EMBED = 6000

EMOJI_CRITICITE = {
    "critique": "🔴",
    "important": "🟠",
    "interessant": "🟡",
    "ignore": "⚪",
}

MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


class DiscordRepository:
    """Wrapper autour d'un webhook Discord (POST JSON)."""

    def __init__(self, webhook_url: str) -> None:
        """Initialise le dépôt et valide l'URL du webhook.

        Args:
            webhook_url: URL HTTPS complète d'un webhook Discord.

        Raises:
            ValueError: Si l'URL n'est pas en HTTPS ou ne pointe pas vers Discord.
        """
        parsee = urlparse(webhook_url)
        if parsee.scheme != "https" or "discord" not in (parsee.netloc or ""):
            raise ValueError("DISCORD_WEBHOOK_URL invalide (HTTPS Discord requis)")
        self._webhook_url = webhook_url

    def publier_digest(self, digest: Digest) -> bool:
        """Publie le Digest sur Discord.

        Args:
            digest: Digest prêt à être publié.

        Returns:
            ``True`` si Discord renvoie HTTP 204, ``False`` sinon.
        """
        payload = {"embeds": [self._construire_embed(digest)]}

        try:
            reponse = requests.post(
                self._webhook_url,
                json=payload,
                timeout=TIMEOUT_HTTP,
            )
        except requests.RequestException as exc:
            logger.error("discord_erreur_reseau", extra={"contexte": {"erreur": str(exc)}})
            return False

        if reponse.status_code == 204:
            logger.info("discord_publication_ok")
            return True

        logger.error(
            "discord_publication_echec",
            extra={"contexte": {"status": reponse.status_code, "body": reponse.text[:200]}},
        )
        return False

    def _construire_embed(self, digest: Digest) -> dict:
        """Construit le dict d'embed conforme aux limites Discord."""
        date_fr = _format_date_fr(digest.date_generation)
        title = _tronquer(f"☀️ Veille du {date_fr}", LIMITE_TITLE)
        stats = (
            f"📊 {digest.nb_articles_analyses} articles analysés • "
            f"{digest.nb_articles_retenus} retenus"
        )
        description = f"**{digest.tldr}**\n\n{stats}" if digest.tldr else stats

        fields: list[dict] = []

        if digest.top_priorites:
            fields.append(
                {
                    "name": "🎯 À lire en priorité",
                    "value": _tronquer(
                        _formater_top(digest.top_priorites), LIMITE_FIELD_VALUE
                    ),
                    "inline": False,
                }
            )

        if digest.autres_articles:
            fields.append(
                {
                    "name": "📚 Autres articles",
                    "value": _tronquer(
                        _formater_autres(digest.autres_articles), LIMITE_FIELD_VALUE
                    ),
                    "inline": False,
                }
            )

        if digest.synthese_journee:
            fields.append(
                {
                    "name": "💡 Synthèse du jour",
                    "value": _tronquer(digest.synthese_journee, LIMITE_FIELD_VALUE),
                    "inline": False,
                }
            )

        embed = {
            "title": title,
            "description": description,
            "color": COULEUR_BLEU,
            "fields": fields,
            "footer": {"text": "Généré par veille-bot"},
            "timestamp": digest.date_generation.isoformat(),
        }

        # Garde-fou final : l'embed total ne doit pas dépasser 6000 caractères.
        if _taille_embed(embed) > LIMITE_TOTAL_EMBED:
            embed["fields"] = embed["fields"][:2]

        return embed


def _formater_top(analyses: list[ArticleAnalyse]) -> str:
    lignes: list[str] = []
    for analyse in analyses:
        emoji = EMOJI_CRITICITE.get(analyse.criticite, "⚪")
        titre = _echapper_markdown(analyse.titre_traduit or analyse.article.titre)
        ligne = (
            f"{emoji} [{titre}]({analyse.article.lien})\n"
            f"   _{analyse.raison_courte}_"
        )
        lignes.append(ligne)
    return "\n\n".join(lignes) or "_Aucune priorité aujourd'hui._"


def _formater_autres(analyses: list[ArticleAnalyse]) -> str:
    lignes: list[str] = []
    for analyse in analyses:
        emoji = EMOJI_CRITICITE.get(analyse.criticite, "⚪")
        titre = _echapper_markdown(analyse.titre_traduit or analyse.article.titre)
        lignes.append(f"• {emoji} [{titre}]({analyse.article.lien})")
    return "\n".join(lignes) or "_Aucun autre article retenu._"


def _echapper_markdown(texte: str) -> str:
    """Échappe les crochets pour ne pas casser la syntaxe lien Markdown."""
    return texte.replace("[", "(").replace("]", ")")


def _tronquer(texte: str, taille_max: int) -> str:
    if len(texte) <= taille_max:
        return texte
    return texte[: taille_max - 1] + "…"


def _taille_embed(embed: dict) -> int:
    total = len(embed.get("title", "")) + len(embed.get("description", ""))
    for field in embed.get("fields", []):
        total += len(field.get("name", "")) + len(field.get("value", ""))
    total += len(embed.get("footer", {}).get("text", ""))
    return total


def _format_date_fr(dt) -> str:
    return f"{dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"
