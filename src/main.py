"""Point d'entrée du bot de veille — câble toutes les couches puis exécute.

Code de sortie 0 en cas de succès, 1 si une exception non gérée a interrompu
le pipeline (utilisable par GitHub Actions pour décider du commit auto).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from src import config as config_module
from src.application.daily_digest_service import DailyDigestService
from src.domain.deduplicator import Deduplicator
from src.infrastructure.discord_repository import DiscordRepository
from src.infrastructure.gemini_repository import GeminiRepository
from src.infrastructure.rss_repository import lire_flux
from src.infrastructure.sqlite_repository import SQLiteRepository
from src.sources import SOURCES


class FormateurJson(logging.Formatter):
    """Formateur JSON minimal pour logs structurés."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        contexte = getattr(record, "contexte", None)
        if contexte is not None:
            payload["contexte"] = contexte
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configurer_logging(niveau: str) -> None:
    """Configure le logging racine en sortie JSON sur stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormateurJson())
    racine = logging.getLogger()
    racine.handlers.clear()
    racine.addHandler(handler)
    racine.setLevel(niveau.upper() if niveau else "INFO")


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
        seen_repo = SQLiteRepository(config.database_path)
        deduplicator = Deduplicator(seen_repo)
        gemini = GeminiRepository(api_key=config.gemini_api_key)
        discord = DiscordRepository(webhook_url=config.discord_webhook_url)

        service = DailyDigestService(
            sources=SOURCES,
            rss_reader=lire_flux,
            deduplicator=deduplicator,
            gemini_repo=gemini,
            discord_repo=discord,
            analyse_repo=seen_repo,
        )
        service.executer()
    except Exception:  # noqa: BLE001 — capture finale, log + exit 1
        logger.critical("execution_interrompue", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
