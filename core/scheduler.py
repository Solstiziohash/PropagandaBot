"""
Scheduler asincrono: invia il report settimanale automaticamente ogni Martedì alle 16:00.
"""

import asyncio
import html
import logging
from datetime import datetime, timedelta, timezone


import aiosqlite
from telegram import Bot
from telegram.constants import ParseMode

from config import ITALY_TZ, TARGET_GROUP_ID, LOGO_PATH, TARGET_TOPIC_ID
from utils.helpers import format_datetime_for_sql, get_week_start, get_week_end
from utils.ui import get_cached_logo, set_cached_logo

logger = logging.getLogger(__name__)


async def _send_weekly_report(bot: Bot, db: aiosqlite.Connection) -> None:
    """Esegue e invia il report settimanale nel gruppo target."""
    logger.info("⏰ Esecuzione Report Automatico...")
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=7)
    start_str = format_datetime_for_sql(start_utc)
    end_str = format_datetime_for_sql(end_utc)

    async with db.execute(
        """SELECT t.admin_id, COUNT(*) as recent_count,
                  GROUP_CONCAT(t.nick, '|') as nick_list,
                  u.last_username, u.first_name
           FROM tesserati t
           LEFT JOIN user_index u ON t.admin_id = u.user_id
           WHERE t.created_at >= ? AND t.created_at < ?
           GROUP BY t.admin_id ORDER BY recent_count DESC LIMIT 10""",
        (start_str, end_str),
    ) as cur:
        results = await cur.fetchall()

    async with db.execute(
        "SELECT COUNT(*) FROM tesserati WHERE created_at >= ? AND created_at < ?",
        (start_str, end_str),
    ) as cur:
        total_week = (await cur.fetchone())[0]

    period_start = start_utc.astimezone(ITALY_TZ).strftime("%d/%m %H:%M")
    period_end = end_utc.astimezone(ITALY_TZ).strftime("%d/%m %H:%M")
    out = (
        f"🚨 <b>REPORT SETTIMANALE AUTOMATICO</b> 🚨\n\n"
        f"<b>Periodo:</b> {period_start} — {period_end}\n\n"
    )

    if not results:
        out += "<i>Nessuna registrazione effettuata questa settimana.</i>"
    else:
        for idx, row in enumerate(results):
            label = (
                row["last_username"] or row["first_name"] or f"id {row['admin_id']}"
            )
            out += f"<b>{idx+1}.</b> {html.escape(label)} — <b>+{row['recent_count']}</b>\n"
        out += (
            f"\n📈 <b>Totale Tesseramenti:</b> {total_week}"
            "\n\n<i>Per i dettagli completi usa /report nel bot privato.</i>"
        )

    photo = get_cached_logo() or open(LOGO_PATH, "rb")
    msg = await bot.send_photo(
        chat_id=TARGET_GROUP_ID,
        photo=photo,
        caption=out,
        parse_mode=ParseMode.HTML,
    )
    if not get_cached_logo() and msg.photo:
        set_cached_logo(msg.photo[-1].file_id)

    await bot.pin_chat_message(TARGET_GROUP_ID, msg.message_id)
    logger.info("✅ Report automatico inviato e fissato.")


async def start_scheduler(bot: Bot, db: aiosqlite.Connection) -> None:
    """Avvia il loop dello scheduler: si attiva ogni Martedì alle 16:00 IT."""

    async def _loop() -> None:
        logger.info("🕒 Scheduler avviato — report automatico ogni Martedì 16:00.")
        while True:
            now_italy = datetime.now(ITALY_TZ)
            days_from_tuesday = (now_italy.weekday() - 1) % 7
            this_tuesday = now_italy.date() - timedelta(days=days_from_tuesday)
            target_time = datetime(
                this_tuesday.year, this_tuesday.month, this_tuesday.day,
                16, 0, 0, tzinfo=ITALY_TZ,
            )
            next_run = (
                target_time + timedelta(days=7)
                if now_italy >= target_time
                else target_time
            )
            sleep_seconds = (next_run - now_italy).total_seconds()
            logger.info(
                "💤 Prossimo report automatico: %s (tra %.0fs)", next_run, sleep_seconds
            )
            await asyncio.sleep(max(sleep_seconds, 0))

            try:
                await _send_weekly_report(bot, db)
            except Exception as exc:
                logger.error("❌ Errore invio report automatico: %s", exc)

            # Attende 70s per evitare doppio invio nello stesso minuto
            await asyncio.sleep(70)

    asyncio.create_task(_loop())
