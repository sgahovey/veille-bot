"""Persistance SQLite des hashes d'articles vus et des analyses retenues.

Implémente les Protocols ``SeenRepository`` (dedup) et ``AnalyseRepository``
(récap hebdo). Toutes les requêtes sont paramétrées (placeholders ``?``)
pour éviter toute injection SQL.

Deux tables coexistent :

- ``seen_articles`` : table historique de déduplication (hash → URL + date vue).
  Sert au filtre ``Deduplicator`` au démarrage de chaque digest quotidien.
- ``articles_analyses`` : table enrichie introduite pour le récap hebdomadaire.
  Stocke chaque analyse Gemini retenue (``garde=True``) avec ses métadonnées
  (criticité, score, raison, titre traduit, lien, source, date_pub, etc.).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from src.domain.models import Article, ArticleAnalyse

logger = logging.getLogger(__name__)

_SCHEMA_SEEN = """
CREATE TABLE IF NOT EXISTS seen_articles (
    hash TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    vu_le TIMESTAMP NOT NULL
)
"""

_SCHEMA_ANALYSES = """
CREATE TABLE IF NOT EXISTS articles_analyses (
    hash_unique TEXT PRIMARY KEY,
    titre TEXT NOT NULL,
    titre_traduit TEXT NOT NULL DEFAULT '',
    resume TEXT NOT NULL DEFAULT '',
    lien TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    date_pub TIMESTAMP NOT NULL,
    categorie_source TEXT NOT NULL DEFAULT 'general',
    garde INTEGER NOT NULL DEFAULT 1,
    criticite TEXT NOT NULL,
    score INTEGER NOT NULL,
    raison_courte TEXT NOT NULL DEFAULT '',
    categorie TEXT NOT NULL,
    enregistre_le TIMESTAMP NOT NULL
)
"""

_INDEX_ANALYSES_DATE_PUB = """
CREATE INDEX IF NOT EXISTS idx_articles_analyses_date_pub
    ON articles_analyses(date_pub)
"""


class SQLiteRepository:
    """Dépôt SQLite — conforme à ``SeenRepository`` et ``AnalyseRepository``."""

    def __init__(self, db_path: str) -> None:
        """Initialise les tables (idempotent : ``IF NOT EXISTS``).

        Args:
            db_path: Chemin du fichier SQLite. Le dossier parent est créé
                automatiquement s'il n'existe pas.
        """
        self._db_path = db_path
        dossier = os.path.dirname(db_path)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        with self._connexion() as conn:
            conn.execute(_SCHEMA_SEEN)
            conn.execute(_SCHEMA_ANALYSES)
            conn.execute(_INDEX_ANALYSES_DATE_PUB)
            conn.commit()

    @contextmanager
    def _connexion(self) -> Iterator[sqlite3.Connection]:
        """Context manager autour d'une connexion SQLite courte durée."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            yield conn
        finally:
            conn.close()

    # ----- SeenRepository ----------------------------------------------------

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

    # ----- AnalyseRepository -------------------------------------------------

    def enregistrer_analyse(self, analyse: ArticleAnalyse) -> None:
        """Persiste une analyse retenue. Idempotent sur ``hash_unique``."""
        article = analyse.article
        try:
            with self._connexion() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO articles_analyses (
                        hash_unique, titre, titre_traduit, resume, lien,
                        source, date_pub, categorie_source,
                        garde, criticite, score, raison_courte, categorie,
                        enregistre_le
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.hash_unique,
                        article.titre,
                        analyse.titre_traduit,
                        article.resume,
                        article.lien,
                        article.source,
                        article.date_pub.isoformat(),
                        article.categorie_source,
                        1 if analyse.garde else 0,
                        analyse.criticite,
                        analyse.score,
                        analyse.raison_courte,
                        analyse.categorie,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            logger.error(
                "sqlite_analyse_erreur",
                extra={"contexte": {"hash": article.hash_unique, "erreur": str(exc)}},
            )

    def lister_gardes_periode(
        self, date_debut: datetime, date_fin: datetime
    ) -> list[ArticleAnalyse]:
        """Retourne toutes les analyses ``garde=True`` entre deux dates (UTC).

        Args:
            date_debut: Borne inférieure inclusive (UTC).
            date_fin: Borne supérieure inclusive (UTC).
        """
        try:
            with self._connexion() as conn:
                curseur = conn.execute(
                    """
                    SELECT hash_unique, titre, titre_traduit, resume, lien,
                           source, date_pub, categorie_source,
                           criticite, score, raison_courte, categorie, garde
                    FROM articles_analyses
                    WHERE garde = 1
                      AND date_pub >= ?
                      AND date_pub <= ?
                    ORDER BY date_pub ASC
                    """,
                    (date_debut.isoformat(), date_fin.isoformat()),
                )
                return [_ligne_vers_analyse(ligne) for ligne in curseur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(
                "sqlite_periode_erreur",
                extra={"contexte": {"erreur": str(exc)}},
            )
            return []


def _ligne_vers_analyse(ligne: tuple) -> ArticleAnalyse:
    """Reconstruit un ``ArticleAnalyse`` complet depuis une ligne SQLite."""
    (
        hash_unique, titre, titre_traduit, resume, lien, source,
        date_pub_iso, categorie_source,
        criticite, score, raison_courte, categorie, garde,
    ) = ligne

    article = Article(
        titre=titre,
        resume=resume,
        lien=lien,
        source=source,
        date_pub=datetime.fromisoformat(date_pub_iso),
        hash_unique=hash_unique,
        categorie_source=categorie_source,
    )
    return ArticleAnalyse(
        article=article,
        garde=bool(garde),
        criticite=criticite,
        score=score,
        raison_courte=raison_courte,
        categorie=categorie,
        titre_traduit=titre_traduit,
    )
