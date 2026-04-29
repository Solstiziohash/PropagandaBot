"""
Funzioni di utilità: date, normalizzazione input, risoluzione utenti.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import aiosqlite
from telegram import Bot

from config import ITALY_TZ

logger = logging.getLogger(__name__)


# ─── DATE ─────────────────────────────────────────────────────────────────────

def get_week_start(dt: datetime) -> datetime:
    """Calcola l'inizio della settimana: martedì alle 16:00 UTC+1."""
    dt_italy = dt.astimezone(ITALY_TZ)
    date = dt_italy.date()
    days_from_tuesday = (date.weekday() - 1) % 7
    this_tuesday = date - timedelta(days=days_from_tuesday)
    reset_point = datetime(
        this_tuesday.year, this_tuesday.month, this_tuesday.day,
        16, 0, 0, tzinfo=ITALY_TZ,
    )
    if dt < reset_point.astimezone(timezone.utc):
        return (reset_point - timedelta(days=7)).astimezone(timezone.utc)
    return reset_point.astimezone(timezone.utc)


def get_week_end(week_start: datetime) -> datetime:
    return week_start + timedelta(days=7)


def format_datetime_for_sql(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_date_ddmmyyyy(input_str: str) -> Optional[datetime]:
    parts = input_str.split("/")
    if len(parts) != 3:
        return None
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime(year, month, day, 12, 0, 0, tzinfo=ITALY_TZ)
    except (ValueError, TypeError):
        return None


# ─── INPUT ────────────────────────────────────────────────────────────────────

def normalize_query(input_str: str) -> Tuple[str, str, int]:
    """
    Restituisce (username_fmt, nick_raw, id_or_minus1).
    La ricerca è case-insensitive: username_fmt e nick_raw sono in minuscolo.
    """
    s = input_str.strip().lower()   # ← case-insensitive
    try:
        id_val = int(s)
    except ValueError:
        id_val = -1

    if s.startswith("@"):
        u = s
    elif all(c.isalnum() or c == "_" for c in s):
        u = f"@{s}"
    else:
        u = s

    return u, s, id_val


# ─── RISOLUZIONE UTENTI ───────────────────────────────────────────────────────

async def resolve_user_id_from_token(
    bot: Bot, db: aiosqlite.Connection, token: str
) -> Optional[int]:
    """Converte un token (@username, username, o ID numerico) in user_id Telegram."""
    t = token.strip()
    try:
        return int(t)
    except ValueError:
        pass
    key = t.lstrip("@").lower()
    async with db.execute(
        "SELECT user_id FROM user_index WHERE username_key = ?", (key,)
    ) as cur:
        row = await cur.fetchone()
    if row:
        return row["user_id"]
    try:
        chat = await bot.get_chat(f"@{key}")
        return chat.id
    except Exception:
        return None


async def resolve_user_label(
    bot: Bot, db: aiosqlite.Connection, user_id: int
) -> str:
    """Restituisce un'etichetta leggibile per un user_id."""
    async with db.execute(
        "SELECT last_username, first_name FROM user_index WHERE user_id=?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    if row:
        return row["last_username"] or row["first_name"] or f"id {user_id}"
    try:
        chat = await bot.get_chat(user_id)
        return (
            f"@{chat.username}" if chat.username
            else (chat.first_name or f"id {user_id}")
        )
    except Exception:
        return f"id {user_id}"
