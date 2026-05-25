"""Tests du déduplicateur avec un faux dépôt en mémoire."""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.deduplicator import Deduplicator
from src.domain.models import Article


class FakeSeenRepository:
    """Implémentation en mémoire du Protocol SeenRepository pour les tests."""

    def __init__(self, deja_vus: set[str] | None = None) -> None:
        self.deja_vus: set[str] = set(deja_vus or set())
        self.marques: list[tuple[str, str]] = []

    def est_deja_vu(self, hash_unique: str) -> bool:
        return hash_unique in self.deja_vus

    def marquer_vu(self, hash_unique: str, url: str) -> None:
        self.deja_vus.add(hash_unique)
        self.marques.append((hash_unique, url))


def _article(hash_unique: str) -> Article:
    return Article(
        titre="t",
        resume="r",
        lien=f"https://example.com/{hash_unique}",
        source="src",
        date_pub=datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc),
        hash_unique=hash_unique,
        categorie_source="general",
    )


def test_filtre_retire_les_articles_deja_vus() -> None:
    repo = FakeSeenRepository(deja_vus={"h2"})
    dedup = Deduplicator(repo)
    articles = [_article("h1"), _article("h2"), _article("h3")]

    resultat = dedup.filtrer_nouveaux(articles)

    assert [a.hash_unique for a in resultat] == ["h1", "h3"]


def test_filtre_retourne_tous_si_tous_nouveaux() -> None:
    repo = FakeSeenRepository()
    dedup = Deduplicator(repo)
    articles = [_article("h1"), _article("h2")]

    assert dedup.filtrer_nouveaux(articles) == articles


def test_filtre_retourne_vide_si_tous_deja_vus() -> None:
    repo = FakeSeenRepository(deja_vus={"h1", "h2"})
    dedup = Deduplicator(repo)
    articles = [_article("h1"), _article("h2")]

    assert dedup.filtrer_nouveaux(articles) == []


def test_marquer_traites_persiste_chaque_hash() -> None:
    repo = FakeSeenRepository()
    dedup = Deduplicator(repo)
    articles = [_article("h1"), _article("h2")]

    dedup.marquer_traites(articles)

    assert repo.deja_vus == {"h1", "h2"}
    assert len(repo.marques) == 2
