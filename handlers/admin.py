"""
Handler per i comandi amministrativi:
  /permesso, /aggiungi_admin, /del_admin, /del_tesserato, /broadcast
"""

import html
import logging
from typing import Optional

import aiosqlite
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from config import (
    PERM_GOD,
    TXT_AUTH_PROPAGANDA,
    BTN_START_AUTH_DATA, BTN_START_AUTH_LABEL,
)
from core.database import get_admin_perm, load_session, save_session, get_all_admin_chat_ids
from core.views import show_main
from utils.helpers import normalize_query, resolve_user_id_from_token, resolve_user_label
from utils.ui import ui_edit_or_send, kb_back_main, kb_broadcast_confirm

logger = logging.getLogger(__name__)


# ─── PERMESSI ─────────────────────────────────────────────────────────────────

async def handle_perm_command(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict,
    perm: int, args: str, reply_user_id: Optional[int],
) -> None:
    parts = args.split()
    if len(parts) == 0:
        target_tok, lvl_opt = None, None
    elif len(parts) == 1:
        try:
            lvl_opt = int(parts[0])
            target_tok = None
        except ValueError:
            target_tok, lvl_opt = parts[0], None
    else:
        target_tok = parts[0]
        try:
            lvl_opt = int(parts[1])
        except ValueError:
            lvl_opt = 1

    req_level = lvl_opt if lvl_opt is not None else 1

    if req_level >= PERM_GOD and perm < PERM_GOD:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⛔ <b>Azione Negata.</b>\n"
            "Solo chi ha il permesso Livello 4 può nominare altri pari grado.",
            kb_back_main(),
        )

    target_id = (
        await resolve_user_id_from_token(bot, db, target_tok)
        if target_tok else reply_user_id
    )

    if not target_id:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⚠️ <b>Utente non trovato o non specificato.</b>",
            kb_back_main(),
        )

    cur_lvl = await get_admin_perm(db, target_id) or 0
    if cur_lvl == PERM_GOD:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⛔ <b>Intoccabile.</b>\n"
            "Nessuno può modificare i permessi di un Livello 4.",
            kb_back_main(),
        )
    if cur_lvl == 3 and perm < PERM_GOD:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⛔ <b>Azione Negata.</b>\n"
            "I Livello 3 non possono modificare altri Livello 3. Serve il Livello 4.",
            kb_back_main(),
        )

    await db.execute(
        "INSERT INTO admins (user_id, perm_level, tesserati_count) VALUES (?,?,0) "
        "ON CONFLICT(user_id) DO UPDATE SET perm_level=excluded.perm_level",
        (target_id, req_level),
    )
    await db.commit()

    stars = {1: "⭐️", 2: "⭐️⭐️", 3: "⭐️⭐️⭐️", 4: "⭐️⭐️⭐️⭐️"}.get(req_level, "⭐️")
    if cur_lvl == 0:
        ts = await load_session(db, target_id)
        try:
            await ui_edit_or_send(
                bot, target_id, ts,
                f"{TXT_AUTH_PROPAGANDA}{stars}",
                InlineKeyboardMarkup([[
                    InlineKeyboardButton(BTN_START_AUTH_LABEL, callback_data=BTN_START_AUTH_DATA)
                ]]),
            )
            await save_session(db, ts)
        except Exception as exc:
            logger.warning("Impossibile notificare utente %s: %s", target_id, exc)

    label = await resolve_user_label(bot, db, target_id)
    await ui_edit_or_send(
        bot, chat_id, s,
        f"✅ <b>Permessi Aggiornati</b>\n\n"
        f"👤 Utente: {html.escape(label)}\n"
        f"⭐ Nuovo Livello: <b>{req_level}</b>\n"
        f"📨 <i>Notifica inviata all'utente.</i>",
        kb_back_main(),
    )


# ─── RIMUOVI ADMIN ────────────────────────────────────────────────────────────

async def handle_del_admin(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict,
    perm: int, args: str, reply_user_id: Optional[int],
) -> None:
    parts = args.split()
    tok = parts[0] if parts else None
    target_id = (
        await resolve_user_id_from_token(bot, db, tok) if tok else reply_user_id
    )

    if not target_id:
        return await ui_edit_or_send(
            bot, chat_id, s, "⚠️ <b>Utente non trovato.</b>", kb_back_main()
        )

    lvl = await get_admin_perm(db, target_id)
    if lvl is None:
        return await ui_edit_or_send(
            bot, chat_id, s, "⚠️ <b>L'utente non è un admin.</b>", kb_back_main()
        )
    if lvl == PERM_GOD:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⛔ <b>DIVINITÀ.</b>\nNessuno può rimuovere un Livello 4.",
            kb_back_main(),
        )
    if lvl == 3 and perm < PERM_GOD:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⛔ <b>Azione Negata.</b>\nSolo un Livello 4 può rimuovere un Livello 3.",
            kb_back_main(),
        )

    await db.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
    await db.commit()
    await ui_edit_or_send(
        bot, chat_id, s, "🗑️ <b>Admin rimosso con successo.</b>", kb_back_main()
    )


# ─── ELIMINA TESSERATO ────────────────────────────────────────────────────────

async def handle_del_tesserato(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict, args: str
) -> None:
    if not args.strip():
        return await ui_edit_or_send(
            bot, chat_id, s,
            "ℹ️ <b>Uso:</b> /del_tesserato ID|@username|nick",
            kb_back_main(),
        )

    u, n, id_val = normalize_query(args.strip())
    async with db.execute(
        "SELECT id, admin_id FROM tesserati "
        "WHERE LOWER(username)=? OR LOWER(nick)=? OR id=? LIMIT 1",
        (u, n, id_val),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return await ui_edit_or_send(
            bot, chat_id, s, "⚠️ <b>Tesserato non trovato.</b>", kb_back_main()
        )

    await db.execute("DELETE FROM tesserati WHERE id=?", (row["id"],))
    await db.execute(
        "UPDATE admins SET tesserati_count = "
        "CASE WHEN tesserati_count > 0 THEN tesserati_count - 1 ELSE 0 END "
        "WHERE user_id=?",
        (row["admin_id"],),
    )
    await db.commit()
    await ui_edit_or_send(
        bot, chat_id, s,
        f"🗑️ <b>Tesserato #{row['id']} eliminato definitivamente.</b>",
        kb_back_main(),
    )


# ─── BROADCAST ────────────────────────────────────────────────────────────────

def format_broadcast_text(raw: str) -> str:
    """Applica il formato predefinito al messaggio broadcast."""
    return (
        "📣 <b>— BROADCAST INTERNO —</b>\n\n"
        f"{html.escape(raw)}"
    )


async def handle_broadcast_command(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict, text: str
) -> None:
    """Mostra l'anteprima del broadcast e chiede conferma."""
    if not text.strip():
        return await ui_edit_or_send(
            bot, chat_id, s,
            "ℹ️ <b>Uso:</b> /broadcast Testo del messaggio...",
            kb_back_main(),
        )

    s["view"] = "BROADCAST_PREVIEW"
    s["broadcast_text"] = text.strip()

    preview = (
        "👁️ <b>Anteprima Broadcast</b>\n"
        "<i>Ecco come apparirà il messaggio agli utenti:</i>\n\n"
        "─────────────────────\n"
        f"{format_broadcast_text(text.strip())}\n"
        "─────────────────────\n\n"
        "Vuoi inviarlo a tutti gli amministratori del bot?"
    )
    await ui_edit_or_send(bot, chat_id, s, preview, kb_broadcast_confirm())
    await save_session(db, s)


async def execute_broadcast(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    """Invia il broadcast a tutti gli admin e torna alla home."""
    raw = s.get("broadcast_text") or ""
    if not raw:
        return await show_main(bot, db, chat_id, s)

    formatted = format_broadcast_text(raw)
    recipients = await get_all_admin_chat_ids(db)

    sent_ok = 0
    sent_fail = 0
    for uid in recipients:
        try:
            await bot.send_message(uid, formatted, parse_mode=ParseMode.HTML)
            sent_ok += 1
        except Exception as exc:
            logger.warning("Broadcast fallito per %s: %s", uid, exc)
            sent_fail += 1

    s["broadcast_text"] = None
    await ui_edit_or_send(
        bot, chat_id, s,
        f"✅ <b>Broadcast inviato!</b>\n\n"
        f"📤 Consegnato: <b>{sent_ok}</b>\n"
        f"❌ Fallito: <b>{sent_fail}</b>",
        kb_back_main(),
    )
    await save_session(db, s)
