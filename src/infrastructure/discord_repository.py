"""Publication du Digest sur Discord via webhook.

Construit un embed riche en respectant les limites de l'API Discord :
title ≤ 256, field.value ≤ 1024, embed total ≤ 6000 caractères, ≤ 25 fields.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from src.domain.models import ArticleAnalyse, Digest, WeeklyRecap

logger = logging.getLogger(__name__)

COULEUR_BLEU = 0x3498DB
COULEUR_ROUGE = 0xE74C3C
COULEUR_VERT = 0x2ECC71
COULEUR_ORANGE = 0xE67E22
COULEUR_VIOLET = 0x9B59B6
COULEUR_GRIS = 0x95A5A6

TIMEOUT_HTTP = 10
LIMITE_TITLE = 256
LIMITE_FIELD_VALUE = 1024
LIMITE_DESCRIPTION = 4096
LIMITE_TOTAL_EMBED = 6000

EMOJI_CRITICITE = {
    "critique": "🔴",
    "important": "🟠",
    "interessant": "🟡",
    "ignore": "⚪",
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
        """Publie le Digest quotidien sur Discord.

        Args:
            digest: Digest prêt à être publié.

        Returns:
            ``True`` si Discord renvoie HTTP 204, ``False`` sinon.
        """
        payload = {"embeds": [self._construire_embed(digest)]}
        return self._post_payload(payload)

    def publier_recap_hebdo(
        self, recap: WeeklyRecap, lien_markdown: str | None = None
    ) -> bool:
        """Publie le récap hebdomadaire sur Discord en multi-embeds.

        Args:
            recap: Récap prêt à être publié.
            lien_markdown: URL publique du fichier Markdown (optionnel). Si fourni,
                un dernier embed pointe vers le fichier sur GitHub.

        Returns:
            ``True`` si Discord renvoie HTTP 204, ``False`` sinon.
        """
        embeds = [
            self._embed_recap_header(recap),
            self._embed_recap_top3(recap),
            self._embed_recap_repartition(recap),
            self._embed_recap_tendances(recap),
            self._embed_recap_a_retenir(recap),
        ]
        if lien_markdown:
            embeds.append(self._embed_recap_markdown(recap, lien_markdown))

        return self._post_payload({"embeds": embeds})

    def _post_payload(self, payload: dict) -> bool:
        """POST un payload JSON sur le webhook, gère les erreurs réseau."""
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


    def _embed_recap_header(self, recap: WeeklyRecap) -> dict:
        """Embed 1 (bleu) — titre, dates, total."""
        debut = _format_date_fr(recap.date_debut)
        fin = _format_date_fr(recap.date_fin)
        return {
            "title": _tronquer(f"📅 Récap veille — {recap.semaine_iso}", LIMITE_TITLE),
            "description": _tronquer(
                f"**Du {debut} au {fin}**\n\n"
                f"📊 **{recap.nb_articles_total}** articles retenus cette semaine",
                LIMITE_DESCRIPTION,
            ),
            "color": COULEUR_BLEU,
            "timestamp": recap.date_generation.isoformat(),
        }

    def _embed_recap_top3(self, recap: WeeklyRecap) -> dict:
        """Embed 2 (rouge) — top 3 articles de la semaine."""
        if not recap.top_3:
            value = "_Pas d'article phare cette semaine._"
        else:
            lignes = []
            for i, analyse in enumerate(recap.top_3, start=1):
                emoji = EMOJI_CRITICITE.get(analyse.criticite, "⚪")
                titre = _echapper_markdown(
                    analyse.titre_traduit or analyse.article.titre
                )
                lignes.append(
                    f"**{i}.** {emoji} [{titre}]({analyse.article.lien})\n"
                    f"   _{analyse.raison_courte}_"
                )
            value = "\n\n".join(lignes)
        return {
            "title": "🏆 Top 3 de la semaine",
            "description": _tronquer(value, LIMITE_DESCRIPTION),
            "color": COULEUR_ROUGE,
        }

    def _embed_recap_repartition(self, recap: WeeklyRecap) -> dict:
        """Embed 3 (vert) — répartition par catégorie."""
        lignes = []
        for cat in ("securite", "backend", "frontend", "devops", "ia", "general"):
            nb = len(recap.par_categorie.get(cat, []))
            if nb == 0:
                continue
            emoji = EMOJI_CATEGORIE.get(cat, "📚")
            label = LIBELLE_CATEGORIE.get(cat, cat.capitalize())
            lignes.append(f"{emoji} **{label}** — {nb}")
        value = "\n".join(lignes) or "_Aucune répartition disponible._"
        return {
            "title": "📊 Répartition par catégorie",
            "description": _tronquer(value, LIMITE_DESCRIPTION),
            "color": COULEUR_VERT,
        }

    def _embed_recap_tendances(self, recap: WeeklyRecap) -> dict:
        """Embed 4 (orange) — tendances de la semaine."""
        return {
            "title": "📈 Tendances de la semaine",
            "description": _tronquer(
                recap.tendances or "_Aucune tendance identifiée._",
                LIMITE_DESCRIPTION,
            ),
            "color": COULEUR_ORANGE,
        }

    def _embed_recap_a_retenir(self, recap: WeeklyRecap) -> dict:
        """Embed 5 (violet) — takeaways actionnables."""
        if not recap.a_retenir:
            value = "_Pas de takeaway cette semaine._"
        else:
            value = "\n".join(
                f"**{i}.** {item}" for i, item in enumerate(recap.a_retenir, start=1)
            )
        return {
            "title": "🎯 À retenir",
            "description": _tronquer(value, LIMITE_DESCRIPTION),
            "color": COULEUR_VIOLET,
        }

    def _embed_recap_markdown(self, recap: WeeklyRecap, lien_markdown: str) -> dict:
        """Embed 6 (gris) — lien vers le fichier Markdown GitHub."""
        return {
            "title": "📁 Récap complet (Markdown)",
            "description": _tronquer(
                f"[Voir sur GitHub]({lien_markdown})",
                LIMITE_DESCRIPTION,
            ),
            "color": COULEUR_GRIS,
        }


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
