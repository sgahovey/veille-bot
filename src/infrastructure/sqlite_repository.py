"""Persistance SQLite des hashes d'articles déjà traités.

Implémente le Protocol ``SeenRepository`` du domaine. Toutes les requêtes
SQL sont paramétrées (placeholders ``?``) — aucune interpolation de chaîne
n'est tolérée pour prévenir toute injection SQL.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_articles (
    hash TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    vu_le TIMESTAMP NOT NULL
)
"""


class SQLiteRepository:
    """Dépôt SQLite des hashes vus, conforme à ``SeenRepository``."""

    def __init__(self, db_path: str) -> None:
        """Initialise le dépôt et crée la table si nécessaire.

        Args:
            db_path: Chemin du fichier SQLite. Le dossier parent est créé
                automatiquement s'il n'existe pas.
        """
        self._db_path = db_path
        dossier = os.path.dirname(db_path)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        with self._connexion() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    @contextmanager
    def _connexion(self) -> Iterator[sqlite3.Connection]:
        """Context manager autour d'une connexion SQLite courte durée."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            yield conn
        finally:
            conn.close()

    def est_deja_vu(self, hash_unique: str) -> bool:
        """Retourne ``True`` si ``hash_unique`` est déjà enregistré."""
        try:
            with self._connexion() as conn:
                curseur = conn.execute(
                    "SELECT 1 FROM seen_articles WHERE hash = ? LIMIT 1",
                    (hash_unique,),
                )
                return curseur.fetchone() is not None
        except sqlite3.Error as exc:
            logger.error(
                "sqlite_lecture_erreur",
                extra={"contexte": {"hash": hash_unique, "erreur": str(exc)}},
            )
            return False

    def marquer_vu(self, hash_unique: str, url: str) -> None:
        """Persiste un hash comme vu (idempotent via INSERT OR IGNORE)."""
        try:
            with self._connexion() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO seen_articles (hash, url, vu_le) "
                    "VALUES (?, ?, ?)",
                    (hash_unique, url, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error(
                "sqlite_ecriture_erreur",
                extra={"contexte": {"hash": hash_unique, "erreur": str(exc)}},
            )

    def purger_anciens(self, jours: int = 90) -> int:
        """Supprime les entrées plus anciennes que ``jours`` jours.

        Returns:
            Nombre de lignes supprimées (0 si erreur).
        """
        seuil = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
        try:
            with self._connexion() as conn:
                curseur = conn.execute(
                    "DELETE FROM seen_articles WHERE vu_le < ?",
                    (seuil,),
                )
                conn.commit()
                return curseur.rowcount or 0
        except sqlite3.Error as exc:
            logger.error("sqlite_purge_erreur", extra={"contexte": {"erreur": str(exc)}})
            return 0
