"""Protocole d'accès aux analyses persistées (utilisé par le récap hebdo).

Le domaine définit l'interface ; l'implémentation concrète vit dans
``src/infrastructure/sqlite_repository.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.models import ArticleAnalyse


class AnalyseRepository(Protocol):
    """Contrat pour persister/requêter les analyses d'articles retenus."""

    def enregistrer_analyse(self, analyse: ArticleAnalyse) -> None:
        """Persiste une analyse retenue. Idempotent sur ``hash_unique``."""
        ...

    def lister_gardes_periode(
        self, date_debut: datetime, date_fin: datetime
    ) -> list[ArticleAnalyse]:
        """Retourne toutes les analyses ``garde=True`` dans l'intervalle.

        Args:
            date_debut: Borne inférieure inclusive (UTC).
            date_fin: Borne supérieure inclusive (UTC).
        """
        ...
