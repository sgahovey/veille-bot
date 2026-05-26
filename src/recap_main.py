"""Point d'entrée du récap hebdomadaire (workflow du dimanche soir).

Equivalent de ``src/main.py`` pour le digest quotidien. Câble toutes les
couches puis exécute ``WeeklyRecapService.executer()``. Code de sortie 0
si tout passe, 1 si une exception non gérée est remontée.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src import config as config_module
from src.application.weekly_recap_service import WeeklyRecapService
from src.infrastructure.discord_repository import DiscordRepository
from src.infrastructure.gemini_repository import GeminiRepository
from src.infrastructure.markdown_exporter import MarkdownExporter
from src.infrastructure.sqlite_repository import SQLiteRepository
from src.main import configurer_logging

REPO_GITHUB_URL = "https://github.com/sgahovey/veille-bot"
DOSSIER_EXPORT_MD = Path("docs/veille")


def main() -> int:
    """Compose et lance le service. Retourne le code de sortie."""
    try:
        config = config_module.charger()
    except ValueError as exc:
        logging.basicConfig(level="ERROR")
        logging.getLogger(__name__).critical("config_invalide : %s", exc)
        return 1

    configurer_logging(config.log_level)
    logger = logging.getLogger(__name__)

    try:
        analyse_repo = SQLiteRepository(config.database_path)
        gemini = GeminiRepository(api_key=config.gemini_api_key)
        discord = DiscordRepository(webhook_url=config.discord_webhook_url)
        exporter = MarkdownExporter()

        service = WeeklyRecapService(
            analyse_repo=analyse_repo,
            gemini_repo=gemini,
            discord_repo=discord,
            markdown_exporter=exporter,
            output_dir=DOSSIER_EXPORT_MD,
            repo_github_url=REPO_GITHUB_URL,
        )
        service.executer()
    except Exception:  # noqa: BLE001
        logger.critical("recap_execution_interrompue", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
