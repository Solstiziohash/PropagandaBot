"""
Gestione database SQLite asincrono.
Tutte le operazioni di lettura/scrittura su DB sono centralizzate qui.
"""

import logging
from typing import Optional

import aiosqlite

from config import DB_FILE

logger = logging.getLogger(__name__)


# ─── INIT ─────────────────────────────────────────────────────────────────────

async def init_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_FILE)
    db.row_factory = aiosqlite.Row
    queries = [
        """CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            perm_level INTEGER NOT NULL DEFAULT 1,
            tesserati_count INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS tesserati (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nick TEXT NOT NULL,
            username TEXT NOT NULL,
            occupation TEXT NOT NULL,
            hours INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS sessions (
            chat_id INTEGER PRIMARY KEY,
            bot_msg_id INTEGER NOT NULL DEFAULT 0,
            view TEXT NOT NULL DEFAULT 'NONE',
            admin_id INTEGER,
            nick TEXT,
            username TEXT,
            occupation TEXT,
            hours INTEGER,
            search_query TEXT,
            search_index INTEGER NOT NULL DEFAULT 0,
            broadcast_text TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS user_system_msgs (
            user_id INTEGER PRIMARY KEY,
            msg_id INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS user_index (
            user_id INTEGER PRIMARY KEY,
            username_key TEXT,
            last_username TEXT,
            first_name TEXT,
            last_name TEXT,
            last_seen TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        "CREATE INDEX IF NOT EXISTS idx_tesserati_created ON tesserati(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_tesserati_hours ON tesserati(hours)",
        "CREATE INDEX IF NOT EXISTS idx_admins_perf ON admins(perm_level, tesserati_count)",
        "CREATE INDEX IF NOT EXISTS idx_user_index_username ON user_index(username_key)",
    ]
    for q in queries:
        await db.execute(q)

    # Migrazione: aggiunta colonna broadcast_text se non esiste (compatibilità DB esistenti)
    try:
        await db.execute("ALTER TABLE sessions ADD COLUMN broadcast_text TEXT")
        await db.commit()
        logger.info("Migrazione DB: aggiunta colonna broadcast_text.")
    except Exception:
        pass  # colonna già presente

    await db.commit()
    return db


# ─── PERMESSI ─────────────────────────────────────────────────────────────────

async def get_admin_perm(db: aiosqlite.Connection, user_id: int) -> Optional[int]:
    async with db.execute(
        "SELECT perm_level FROM admins WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
        return row["perm_level"] if row else None


# ─── SESSIONI ─────────────────────────────────────────────────────────────────

async def load_session(db: aiosqlite.Connection, chat_id: int) -> dict:
    async with db.execute(
        "SELECT * FROM sessions WHERE chat_id = ?", (chat_id,)
    ) as cur:
        row = await cur.fetchone()
    if row:
        return dict(row)
    return {
        "chat_id": chat_id,
        "bot_msg_id": 0,
        "view": "NONE",
        "admin_id": None,
        "nick": None,
        "username": None,
        "occupation": None,
        "hours": None,
        "search_query": None,
        "search_index": 0,
        "broadcast_text": None,
    }


async def save_session(db: aiosqlite.Connection, s: dict):
    await db.execute(
        """INSERT INTO sessions
           (chat_id, bot_msg_id, view, admin_id, nick, username, occupation,
            hours, search_query, search_index, broadcast_text)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(chat_id) DO UPDATE SET
           bot_msg_id=excluded.bot_msg_id, view=excluded.view,
           admin_id=excluded.admin_id, nick=excluded.nick,
           username=excluded.username, occupation=excluded.occupation,
           hours=excluded.hours, search_query=excluded.search_query,
           search_index=excluded.search_index,
           broadcast_text=excluded.broadcast_text""",
        (
            s["chat_id"], s["bot_msg_id"], s["view"], s["admin_id"],
            s["nick"], s["username"], s["occupation"], s["hours"],
            s["search_query"], s["search_index"],
            s.get("broadcast_text"),
        ),
    )
    await db.commit()


# ─── USER INDEX ───────────────────────────────────────────────────────────────

async def index_user(db: aiosqlite.Connection, user) -> None:
    """Aggiorna la cache username→user_id per la ricerca utenti."""
    user_id = user.id
    username_key = (
        user.username.strip().lstrip("@").lower() if user.username else None
    )
    last_username = (
        f"@{user.username.strip().lstrip('@')}" if user.username else None
    )
    await db.execute(
        """INSERT INTO user_index
           (user_id, username_key, last_username, first_name, last_name, last_seen)
           VALUES (?,?,?,?,?,datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
           username_key=excluded.username_key,
           last_username=excluded.last_username,
           first_name=excluded.first_name,
           last_name=excluded.last_name,
           last_seen=datetime('now')""",
        (user_id, username_key, last_username, user.first_name, user.last_name),
    )
    await db.commit()


# ─── TESSERATI ────────────────────────────────────────────────────────────────

async def get_all_admin_chat_ids(db: aiosqlite.Connection) -> list[int]:
    """Restituisce la lista di tutti gli user_id admin per il broadcast."""
    async with db.execute("SELECT user_id FROM admins") as cur:
        rows = await cur.fetchall()
    return [row["user_id"] for row in rows]

async def reset_bot_msg_id(db: aiosqlite.Connection, chat_id: int) -> None:
    await db.execute(
        "UPDATE sessions SET bot_msg_id = 0 WHERE chat_id = ?", (chat_id,)
    )
    await db.commit()
