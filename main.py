"""
Entry point del Bot Telegram — Reparto Propaganda di Progresso Riformista.

"""

import asyncio
import logging
import sys

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from core.database import init_db
from core.scheduler import start_scheduler
from handlers.callbacks import handle_callback
from handlers.messages import handle_message

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ─── COMANDI REGISTRATI ───────────────────────────────────────────────────────

REGISTERED_COMMANDS = [
    "start",
    "guida",
    "scheda",
    "classifica_ore",
    "classifica_admin",
    "lista_tesserati",
    "lista_admin",
    "report",
    "permesso",
    "aggiungi_admin",
    "del_admin",
    "del_tesserato",
    "broadcast",
]


# ─── POST-INIT ────────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN non impostato! Verifica il file .env.")
        sys.exit(1)

    db = await init_db()
    application.bot_data["db"] = db
    await start_scheduler(application.bot, db)
    logger.info("🚀 Bot avviato correttamente.")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Comandi espliciti → handle_message gestisce tutto internamente
    app.add_handler(
        CommandHandler(REGISTERED_COMMANDS, handle_message)
    )
    # Testo libero (wizard)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    # Callback inline
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()