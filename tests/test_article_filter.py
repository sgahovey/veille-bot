"""Tests du filtrage 24h — fonction pure, aucun mock requis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.domain.article_filter import filtrer_dernieres_24h
from src.domain.models import Article


def _article(date_pub: datetime, hash_unique: str = "h") -> Article:
    return Article(
        titre="t",
        resume="r",
        lien="https://example.com",
        source="src",
        date_pub=date_pub,
        hash_unique=hash_unique,
        categorie_source="general",
    )


def test_article_recent_de_5h_est_garde() -> None:
    maintenant = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    article = _article(maintenant - timedelta(hours=5), "h1")
    assert filtrer_dernieres_24h([article], maintenant) == [article]


def test_article_de_23h_est_garde() -> None:
    maintenant = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    article = _article(maintenant - timedelta(hours=23), "h2")
    assert filtrer_dernieres_24h([article], maintenant) == [article]


def test_article_de_25h_est_exclu() -> None:
    maintenant = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    article = _article(maintenant - timedelta(hours=25), "h3")
    assert filtrer_dernieres_24h([article], maintenant) == []


def test_liste_vide_retourne_liste_vide() -> None:
    maintenant = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    assert filtrer_dernieres_24h([], maintenant) == []
