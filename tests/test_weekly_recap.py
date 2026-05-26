"""Tests de la dataclass WeeklyRecap (construction, defaults, immutabilité)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from src.domain.models import Article, ArticleAnalyse, WeeklyRecap


def _analyse(hash_unique: str, criticite: str, categorie: str, score: int) -> ArticleAnalyse:
    article = Article(
        titre=f"Titre {hash_unique}",
        resume="r",
        lien=f"https://example.com/{hash_unique}",
        source="src",
        date_pub=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        hash_unique=hash_unique,
        categorie_source=categorie,
    )
    return ArticleAnalyse(
        article=article,
        garde=True,
        criticite=criticite,
        score=score,
        raison_courte="ok",
        categorie=categorie,
        titre_traduit=f"Titre traduit {hash_unique}",
    )


def test_weekly_recap_construction_minimale() -> None:
    debut = datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    fin = datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc)
    recap = WeeklyRecap(
        semaine_iso="2026-W22",
        date_debut=debut,
        date_fin=fin,
        nb_articles_total=0,
    )
    assert recap.semaine_iso == "2026-W22"
    assert recap.top_3 == []
    assert recap.par_categorie == {}
    assert recap.a_retenir == []
    assert recap.tendances == ""


def test_weekly_recap_avec_top3_et_repartition() -> None:
    a1 = _analyse("h1", "critique", "securite", 10)
    a2 = _analyse("h2", "important", "backend", 8)
    a3 = _analyse("h3", "interessant", "frontend", 6)

    recap = WeeklyRecap(
        semaine_iso="2026-W22",
        date_debut=datetime(2026, 5, 25, tzinfo=timezone.utc),
        date_fin=datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        nb_articles_total=3,
        top_3=[a1, a2, a3],
        par_categorie={"securite": [a1], "backend": [a2], "frontend": [a3]},
        tendances="Forte activité sécurité cette semaine.",
        a_retenir=["MAJ Symfony", "Lire OWASP XSS", "Tester PHP 8.4"],
    )

    assert recap.top_3[0].article.hash_unique == "h1"
    assert recap.par_categorie["backend"][0].score == 8
    assert len(recap.a_retenir) == 3


def test_weekly_recap_est_immuable() -> None:
    recap = WeeklyRecap(
        semaine_iso="2026-W22",
        date_debut=datetime(2026, 5, 25, tzinfo=timezone.utc),
        date_fin=datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        nb_articles_total=0,
    )
    with pytest.raises(FrozenInstanceError):
        recap.nb_articles_total = 5  # type: ignore[misc]
