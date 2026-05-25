"""Chargement de la configuration applicative depuis l'environnement.

En développement local, ``python-dotenv`` lit un fichier ``.env`` si présent.
En CI/CD, les variables sont injectées par GitHub Actions (Secrets).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

FENETRE_HEURES = 24
MAX_TOP_PRIORITES = 3
RSS_TIMEOUT = 10

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Valeurs de configuration résolues au démarrage."""

    gemini_api_key: str
    discord_webhook_url: str
    database_path: str
    log_level: str


def charger() -> Config:
    """Charge et valide la configuration depuis les variables d'environnement.

    Returns:
        Une instance de ``Config`` immuable.

    Raises:
        ValueError: Si une variable obligatoire est absente ou vide.
    """
    gemini = os.environ.get("GEMINI_API_KEY", "").strip()
    discord = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    db_path = os.environ.get("DATABASE_PATH", "data/seen.db").strip()
    log_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()

    manquantes: list[str] = []
    if not gemini:
        manquantes.append("GEMINI_API_KEY")
    if not discord:
        manquantes.append("DISCORD_WEBHOOK_URL")
    if manquantes:
        raise ValueError(
            "Variables d'environnement obligatoires manquantes : "
            + ", ".join(manquantes)
        )

    return Config(
        gemini_api_key=gemini,
        discord_webhook_url=discord,
        database_path=db_path,
        log_level=log_level,
    )
