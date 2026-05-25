"""Filtrage temporel des articles — fonction pure, sans I/O."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.models import Article

FENETRE_HEURES_DEFAUT = 24


def filtrer_dernieres_24h(
    articles: list[Article],
    maintenant: datetime,
    fenetre_heures: int = FENETRE_HEURES_DEFAUT,
) -> list[Article]:
    """Retourne uniquement les articles publiés dans les ``fenetre_heures`` dernières heures.

    Cette fonction est strictement pure : aucun appel réseau, aucune lecture
    système. Elle est entièrement testable sans mock.

    Args:
        articles: Liste d'articles candidats.
        maintenant: Référence temporelle "maintenant" (UTC recommandé).
        fenetre_heures: Taille de la fenêtre glissante en heures (défaut 24).

    Returns:
        Sous-ensemble d'articles dont ``date_pub >= maintenant - fenetre``.

    Note:
        Si ``date_pub`` est naïf (sans tzinfo), il est traité comme UTC pour
        permettre la comparaison avec ``maintenant`` (qui peut être tz-aware).
    """
    if not articles:
        return []

    seuil = maintenant - timedelta(hours=fenetre_heures)
    seuil_tz = _normaliser_utc(seuil)

    return [
        article
        for article in articles
        if _normaliser_utc(article.date_pub) >= seuil_tz
    ]


def _normaliser_utc(dt: datetime) -> datetime:
    """Force un datetime en tz-aware UTC pour permettre les comparaisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
