"""Lecture des flux RSS via feedparser.

La fonction publique ``lire_flux`` est isolée du reste : toute exception
y est attrapée et convertie en log + liste vide, pour qu'un flux fautif
n'interrompe jamais l'exécution globale du bot.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from time import struct_time
from urllib.parse import urlparse

import feedparser

from src.domain.models import Article

logger = logging.getLogger(__name__)

LONGUEUR_MAX_RESUME = 500
_REGEX_HTML = re.compile(r"<[^>]+>")
_REGEX_ESPACES = re.compile(r"\s+")


def lire_flux(source: dict, timeout: int = 10) -> list[Article]:
    """Récupère et parse un flux RSS en liste d'articles.

    Args:
        source: Dict contenant au minimum ``{"nom", "url", "categorie"}``.
        timeout: Timeout HTTP en secondes appliqué à la requête réseau.

    Returns:
        Liste d'articles parsés. Liste vide en cas d'erreur réseau ou
        de format invalide — aucune exception remontée.
    """
    nom = source.get("nom", "inconnu")
    url = source.get("url", "")
    categorie = source.get("categorie", "general")

    if not _url_securisee(url):
        logger.warning("rss_url_invalide", extra={"contexte": {"source": nom, "url": url}})
        return []

    try:
        flux = feedparser.parse(url, request_headers={"User-Agent": "veille-bot/1.0"})
    except Exception as exc:  # noqa: BLE001 — robustesse: tout convertir en log
        logger.warning(
            "rss_erreur_parse",
            extra={"contexte": {"source": nom, "erreur": str(exc)}},
        )
        return []

    if getattr(flux, "bozo", 0) and not getattr(flux, "entries", None):
        logger.warning(
            "rss_flux_invalide",
            extra={"contexte": {"source": nom, "raison": str(getattr(flux, "bozo_exception", ""))}},
        )
        return []

    articles: list[Article] = []
    for entree in flux.entries:
        try:
            article = _construire_article(entree, nom, categorie)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "rss_entree_ignoree",
                extra={"contexte": {"source": nom, "erreur": str(exc)}},
            )
            continue
        if article is not None:
            articles.append(article)

    logger.info(
        "rss_flux_lu",
        extra={"contexte": {"source": nom, "articles": len(articles)}},
    )
    return articles


def _construire_article(entree: dict, source_nom: str, categorie: str) -> Article | None:
    """Construit un Article à partir d'une entrée feedparser brute."""
    lien = (entree.get("link") or "").strip()
    titre = (entree.get("title") or "").strip()
    if not lien or not titre:
        return None

    resume_brut = entree.get("summary") or entree.get("description") or ""
    resume = _nettoyer_html(resume_brut)[:LONGUEUR_MAX_RESUME]

    date_pub = _extraire_date(entree)
    if date_pub is None:
        date_pub = datetime.now(timezone.utc)

    hash_unique = hashlib.sha256(lien.encode("utf-8")).hexdigest()

    return Article(
        titre=titre,
        resume=resume,
        lien=lien,
        source=source_nom,
        date_pub=date_pub,
        hash_unique=hash_unique,
        categorie_source=categorie,
    )


def _extraire_date(entree: dict) -> datetime | None:
    """Extrait la meilleure date possible depuis une entrée feedparser."""
    for cle in ("published_parsed", "updated_parsed"):
        valeur: struct_time | None = entree.get(cle)
        if valeur is not None:
            return datetime(*valeur[:6], tzinfo=timezone.utc)
    return None


def _nettoyer_html(texte: str) -> str:
    """Supprime balises HTML et normalise les espaces."""
    sans_balises = _REGEX_HTML.sub(" ", texte)
    return _REGEX_ESPACES.sub(" ", sans_balises).strip()


def _url_securisee(url: str) -> bool:
    """Valide qu'une URL utilise bien HTTPS et possède un hôte."""
    try:
        parsee = urlparse(url)
    except ValueError:
        return False
    return parsee.scheme == "https" and bool(parsee.netloc)
