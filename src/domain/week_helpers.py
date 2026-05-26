"""Helpers temporels pour le récap hebdomadaire — fonctions pures."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone


def bornes_semaine_iso(reference: datetime) -> tuple[datetime, datetime]:
    """Retourne le lundi 00:00 UTC et le dimanche 23:59:59 UTC de la semaine ISO.

    La semaine ISO commence le lundi (jour 1) et se termine le dimanche (jour 7).

    Args:
        reference: Date de référence (n'importe quel moment dans la semaine).

    Returns:
        Tuple ``(lundi_00h00_utc, dimanche_23h59_utc)`` tous deux tz-aware UTC.
    """
    ref_utc = _normaliser_utc(reference)
    jours_depuis_lundi = ref_utc.weekday()  # lundi = 0
    lundi_date = (ref_utc - timedelta(days=jours_depuis_lundi)).date()
    dimanche_date = lundi_date + timedelta(days=6)

    debut = datetime.combine(lundi_date, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(dimanche_date, time(23, 59, 59), tzinfo=timezone.utc)
    return debut, fin


def libelle_semaine_iso(reference: datetime) -> str:
    """Retourne l'identifiant ISO de la semaine au format ``"YYYY-Wnn"``.

    Args:
        reference: Date de référence.

    Returns:
        Chaîne au format ``"2026-W21"``.
    """
    annee, semaine, _ = _normaliser_utc(reference).isocalendar()
    return f"{annee}-W{semaine:02d}"


def _normaliser_utc(dt: datetime) -> datetime:
    """Force un datetime en tz-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
