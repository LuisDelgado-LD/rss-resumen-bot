"""
Punto de entrada de producción para el bot interactivo de Telegram.

Arranca el TelegramBot con todos sus clientes reales (Wallabag, TT-RSS via
state persistido, etc.) y entra al loop de polling.

Uso:
    python -m src.bot_runner          # Producción con Wallabag real
    python -m src.bot_runner --no-wallabag  # Sin Wallabag (solo log)

En Docker:
    CMD ["python", "-m", "src.bot_runner"]
"""
import sys
import argparse
from pathlib import Path

from src.config import settings
from src.utils.logger import logger
from src.db import StateManager
from src.clients import TelegramClient, TTRSSClient
from src.bot import TelegramBot


def main() -> int:
    logger.debug("→ bot_runner.main()")

    parser = argparse.ArgumentParser(description="RSS Digest Bot - modo interactivo")
    parser.add_argument(
        "--no-wallabag",
        action="store_true",
        help="Deshabilitar Wallabag (registra solo log, no guarda realmente)",
    )
    args = parser.parse_args()

    # ── Validar configuración ────────────────────────────────────────────────
    is_valid, errors = settings.validate()
    if not is_valid:
        logger.error("❌ Configuración inválida:")
        for err in errors:
            logger.error(f"  - {err}")
        return 1

    # ── Clientes ─────────────────────────────────────────────────────────────
    telegram_client = TelegramClient(bot_token=settings.TELEGRAM_BOT_TOKEN)
    state_manager   = StateManager()

    # TT-RSS: cliente real para poder marcar artículos como leídos
    article_meta = state_manager.load_article_metadata()

    ttrss_client = TTRSSClient(
        url=settings.TTRSS_URL,
        username=settings.TTRSS_USER,
        password=settings.TTRSS_PASSWORD,
    )
    ttrss_client.login()

    # Wallabag (real o dummy)
    if args.no_wallabag:
        class _DummyWallabagClient:
            def save_article(self, url, title=None, tags=None):
                logger.info(f"[NO-WALLABAG] Simulado guardado: {url}")
                return {"status": "simulado", "url": url}

        wallabag_client = _DummyWallabagClient()
        logger.info("⚠️  Wallabag deshabilitado (--no-wallabag)")
    else:
        try:
            from src.clients.wallabag_client import WallabagClient
            wallabag_client = WallabagClient()
            logger.info("✅ WallabagClient inicializado")
        except Exception as e:
            logger.warning(f"⚠️  No se pudo inicializar Wallabag: {e} — usando DummyWallabagClient")

            class _DummyWallabagClient:
                def save_article(self, url, title=None, tags=None):
                    logger.info(f"[NO-WALLABAG] Simulado guardado: {url}")
                    return {"status": "simulado", "url": url}

            wallabag_client = _DummyWallabagClient()

    # ── Arranque ─────────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("🤖 INICIANDO BOT INTERACTIVO")
    logger.info("=" * 70)
    logger.info(f"Modo Telegram : {settings.TELEGRAM_MODE}")
    logger.info(f"URLs en estado: {len(article_meta)} entradas")
    if not article_meta:
        logger.warning("⚠️  No hay URLs persistidas. Ejecuta el digest primero")
    logger.info("=" * 70)

    bot = TelegramBot(
        telegram_client=telegram_client,
        ttrss_client=ttrss_client,
        state_manager=state_manager,
        wallabag_client=wallabag_client,
        summaries=None,
        articles_by_category=None,
    )

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("⚠️  Bot detenido por el usuario")
    finally:
        ttrss_client.logout()

    logger.debug("← bot_runner.main()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
