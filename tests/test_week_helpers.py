"""Tests des helpers de semaine ISO — fonctions pures."""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.week_helpers import bornes_semaine_iso, libelle_semaine_iso


def test_bornes_semaine_iso_pour_un_mercredi() -> None:
    # Mercredi 27 mai 2026 → semaine ISO 22 → lundi 25 mai au dimanche 31 mai.
    reference = datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc)
    debut, fin = bornes_semaine_iso(reference)

    assert debut == datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc)


def test_bornes_semaine_iso_pour_un_lundi_a_minuit() -> None:
    reference = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    debut, fin = bornes_semaine_iso(reference)
    assert debut == reference
    assert fin == datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc)


def test_bornes_semaine_iso_pour_un_dimanche_a_19h() -> None:
    # Dimanche 31 mai 2026 à 19h → reste dans la même semaine ISO 22.
    reference = datetime(2026, 5, 31, 19, 0, tzinfo=timezone.utc)
    debut, fin = bornes_semaine_iso(reference)
    assert debut == datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc)


def test_bornes_normalise_un_datetime_naif_en_utc() -> None:
    reference_naive = datetime(2026, 5, 27, 14, 30)
    debut, fin = bornes_semaine_iso(reference_naive)
    assert debut.tzinfo is not None
    assert fin.tzinfo is not None


def test_libelle_semaine_iso_format_attendu() -> None:
    reference = datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc)
    assert libelle_semaine_iso(reference) == "2026-W22"


def test_libelle_semaine_iso_padding_a_deux_chiffres() -> None:
    # Première semaine de l'année 2026 → "2026-W01"
    reference = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    assert libelle_semaine_iso(reference) == "2026-W02"  # 2026-01-05 est lundi de S2
