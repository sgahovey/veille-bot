"""Déduplication des articles via un dépôt abstrait (Protocol).

L'inversion de dépendance permet au domaine de rester découplé de SQLite :
la couche infrastructure fournit une implémentation concrète qui satisfait
le Protocol ``SeenRepository``.
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.models import Article

logger = logging.getLogger(__name__)


class SeenRepository(Protocol):
    """Contrat pour un dépôt de hashes d'articles déjà vus."""

    def est_deja_vu(self, hash_unique: str) -> bool:
        """Retourne ``True`` si le hash a déjà été enregistré."""
        ...

    def marquer_vu(self, hash_unique: str, url: str) -> None:
        """Persiste un hash comme vu, associé à son URL d'origine."""
        ...


class Deduplicator:
    """Filtre les articles déjà traités lors d'exécutions précédentes."""

    def __init__(self, repo: SeenRepository) -> None:
        """Initialise le déduplicateur.

        Args:
            repo: Implémentation du Protocol ``SeenRepository``.
        """
        self._repo = repo

    def filtrer_nouveaux(self, articles: list[Article]) -> list[Article]:
        """Retourne uniquement les articles dont le hash est inconnu du dépôt.

        Args:
            articles: Liste d'articles candidats.

        Returns:
            Articles dont ``hash_unique`` n'est pas encore enregistré.
        """
        nouveaux: list[Article] = []
        for article in articles:
            if not self._repo.est_deja_vu(article.hash_unique):
                nouveaux.append(article)
        logger.info(
            "deduplication",
            extra={"contexte": {"entree": len(articles), "nouveaux": len(nouveaux)}},
        )
        return nouveaux

    def marquer_traites(self, articles: list[Article]) -> None:
        """Enregistre une liste d'articles comme traités.

        Args:
            articles: Articles dont le hash doit être persisté.
        """
        for article in articles:
            self._repo.marquer_vu(article.hash_unique, article.lien)
