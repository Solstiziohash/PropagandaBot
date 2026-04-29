"""
Handler per tutti i callback query (bottoni inline).
"""

import asyncio
import logging
import html

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes
from utils.ui import (
    ui_edit_or_send, kb_empty, kb_not_admin, kb_main,
    kb_wizard_back, kb_confirm, kb_back_main,
)

from config import (
    CTX_REPORT, VIEW_REPORT, VIEW_SCHEDA,
    VIEW_LEADERBOARD_HOURS, VIEW_LEADERBOARD_ADMINS,
    VIEW_LIST_ADMINS, VIEW_LIST_TESSERATI,
    BTN_RECHECK_DATA, BTN_START_AUTH_DATA, BTN_BACK_MAIN_DATA,
    BTN_GUIDE_DATA, BTN_REGISTER_DATA,
    BTN_SEND_DATA, BTN_REDO_DATA,
    BTN_PREV_DATA, BTN_NEXT_DATA,
    BTN_BACK_TO_START, BTN_BACK_TO_1, BTN_BACK_TO_2, BTN_BACK_TO_3,
    BTN_BACK_REPORT_DATA,
    BTN_BROADCAST_CONFIRM_DATA, BTN_BROADCAST_CANCEL_DATA,
    BTN_BACK_TO_START,
)
from core.database import get_admin_perm, load_session, save_session
from core.views import (
    show_main, show_guide,
    render_scheda_page, render_report_page,
    render_leaderboard_hours, render_list_generic,
)
from handlers.admin import execute_broadcast
from utils.subscription import check_subscription
from utils.ui import (
    ui_edit_or_send, kb_empty, kb_not_admin, kb_main,
    kb_wizard_back, kb_confirm,
)
from config import BTN_BACK_TO_1, BTN_BACK_TO_2, BTN_BACK_TO_3
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Viste con paginazione — mappa testo caption → view
_CAPTION_VIEW_MAP = {
    "Report Settimanale": VIEW_REPORT,
    "Fascicolo": VIEW_SCHEDA,
    "Classifica Ore": VIEW_LEADERBOARD_HOURS,
    "Classifica Produttività": VIEW_LEADERBOARD_ADMINS,
    "Lista Amministratori": VIEW_LIST_ADMINS,
    "Registro Tesserati": VIEW_LIST_TESSERATI,
}


def _infer_view_from_caption(txt: str) -> str | None:
    for keyword, view in _CAPTION_VIEW_MAP.items():
        if keyword in txt:
            return view
    return None


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: aiosqlite.Connection = context.bot_data["db"]
    q = update.callback_query
    if not q or not q.data:
        return

    data = q.data
    chat_id = q.message.chat_id if q.message else 0
    uid = q.from_user.id

    # ── Verifica iscrizione canale ─────────────────────────────────────────────
    if data == "check_sub":
        if await check_subscription(context.bot, uid):
            try:
                await context.bot.delete_message(chat_id, q.message.message_id)
            except Exception:
                pass
            sent = await context.bot.send_message(
                uid,
                "✅ <b>Ti sei iscritto!</b>\n<i>Digita /start per iniziare.</i>",
                parse_mode=ParseMode.HTML,
            )
            await db.execute(
                "INSERT OR REPLACE INTO user_system_msgs (user_id, msg_id) VALUES (?,?)",
                (uid, sent.message_id),
            )
            await db.commit()
        else:
            await q.answer("❌ Non risulti ancora iscritto al canale.", show_alert=True)
        return

    s = await load_session(db, chat_id)
    if q.message:
        s["bot_msg_id"] = q.message.message_id
    perm = await get_admin_perm(db, uid)

    # ── Verifica permessi ──────────────────────────────────────────────────────
    if data == BTN_RECHECK_DATA:
        if perm is not None:
            await ui_edit_or_send(
                context.bot, chat_id, s,
                (
                    "<b>✅ Autenticazione Riuscita!</b>\n\n"
                    "I tuoi permessi sono stati aggiornati. "
                    "Ora hai accesso alle funzionalità del Bot."
                ),
                kb_empty(),
            )
            await save_session(db, s)
            await asyncio.sleep(2)
            await show_main(context.bot, db, chat_id, s)
        else:
            await context.bot.send_message(
                chat_id, "❌ Non risulti ancora un amministratore."
            )
        await q.answer()

    # ── Home / start_from_auth ─────────────────────────────────────────────────
    elif data in (BTN_START_AUTH_DATA, BTN_BACK_MAIN_DATA):
        if perm is not None:
            await show_main(context.bot, db, chat_id, s)
        else:
            await ui_edit_or_send(
                context.bot, chat_id, s,
                (
                    "<b>🚫 Accesso Negato</b>\n\n"
                    "Non risulti essere un amministratore autorizzato.\n"
                    "<i>Contatta un superiore per richiedere l'accesso.</i>"
                ),
                kb_not_admin(),
            )
            await save_session(db, s)
        await q.answer()

    # ── Guida ─────────────────────────────────────────────────────────────────
    elif data == BTN_GUIDE_DATA:
        if perm is not None:
            await show_guide(context.bot, db, chat_id, s, perm)
        await q.answer()

    # ── Wizard: inizio registrazione ──────────────────────────────────────────
    elif data == BTN_REGISTER_DATA:
        s.update({
            "view": "W_NICK",
            "admin_id": uid,
            "nick": None, "username": None,
            "occupation": None, "hours": None,
        })
        await ui_edit_or_send(
            context.bot, chat_id, s,
            "1️⃣ <b>Inserisci il Nickname del Tesserato</b>",
            kb_wizard_back(BTN_BACK_TO_START),
        )
        await save_session(db, s)
        await q.answer()

    # ── Wizard: conferma invio ─────────────────────────────────────────────────
    elif data == BTN_SEND_DATA:
        if s["view"] == "CONFIRM":
            aid = s["admin_id"] or uid

            # Controllo duplicati
            async with db.execute(
                "SELECT id, nick FROM tesserati WHERE LOWER(username) = LOWER(?) OR LOWER(nick) = LOWER(?)",
                (s["username"], s["nick"]),
            ) as cur:
                existing = await cur.fetchone()

            if existing:
                await ui_edit_or_send(
                    context.bot, chat_id, s,
                    f"⚠️ <b>Tesserato già presente!</b>\n\n"
                    f"Esiste già un profilo con questo nick o username.\n"
                    f"ID nel database: <b>#{existing['id']}</b> — <b>{html.escape(existing['nick'])}</b>\n\n"
                    f"Usa /scheda per visualizzarlo.",
                    kb_back_main(),
                )
                await save_session(db, s)
                await q.answer()
                return

            # Inserimento
            await db.execute(
                "INSERT INTO tesserati (nick, username, occupation, hours, admin_id) "
                "VALUES (?,?,?,?,?)",
                (s["nick"], s["username"], s["occupation"], s["hours"], aid),
            )
            await db.execute(
                "UPDATE admins SET tesserati_count=tesserati_count+1 WHERE user_id=?",
                (aid,),
            )
            await db.commit()
            await ui_edit_or_send(
                context.bot, chat_id, s,
                "<b>✅ Registrazione completata con successo!</b>\n\n"
                "Il tesserato è stato aggiunto al database.",
                kb_empty(),
            )
            await save_session(db, s)
            await asyncio.sleep(2)
            await show_main(context.bot, db, chat_id, s)
        await q.answer()
    # ── Torna al report ────────────────────────────────────────────────────────
    elif data == BTN_BACK_REPORT_DATA:
        s["search_index"] = int(s.get("hours") or 0)
        s["occupation"] = None
        await save_session(db, s)
        await render_report_page(context.bot, db, chat_id, s)
        await q.answer()

    # ── Paginazione ───────────────────────────────────────────────────────────
    elif data in (BTN_PREV_DATA, BTN_NEXT_DATA):
        if q.message:
            caption_txt = (
                getattr(q.message, "caption", None) or
                getattr(q.message, "text", None) or ""
            )
            inferred = _infer_view_from_caption(caption_txt)
            if inferred:
                s["view"] = inferred

        s["search_index"] += 1 if data == BTN_NEXT_DATA else -1
        await save_session(db, s)

        view = s["view"]
        if view == VIEW_SCHEDA:
            await render_scheda_page(context.bot, db, chat_id, s)
        elif view == VIEW_REPORT:
            await render_report_page(context.bot, db, chat_id, s)
        elif view == VIEW_LEADERBOARD_HOURS:
            await render_leaderboard_hours(context.bot, db, chat_id, s)
        else:
            await render_list_generic(context.bot, db, chat_id, s)

        await save_session(db, s)
        await q.answer()

    # ── Wizard: pulsanti indietro ──────────────────────────────────────────────
    elif data == BTN_BACK_TO_START:
        await show_main(context.bot, db, chat_id, s)
        await q.answer()

    elif data == BTN_BACK_TO_1:
        s["view"] = "W_NICK"
        await ui_edit_or_send(
            context.bot, chat_id, s,
            "1️⃣ <b>Inserisci il Nickname del Tesserato</b>",
            kb_wizard_back(BTN_BACK_TO_START),
        )
        await save_session(db, s)
        await q.answer()

    elif data == BTN_BACK_TO_2:
        s["view"] = "W_USER"
        await ui_edit_or_send(
            context.bot, chat_id, s,
            "2️⃣ <b>Inserisci l'Username</b>",
            kb_wizard_back(BTN_BACK_TO_1),
        )
        await save_session(db, s)
        await q.answer()

    elif data == BTN_BACK_TO_3:
        s["view"] = "W_OCC"
        await ui_edit_or_send(
            context.bot, chat_id, s,
            "3️⃣ <b>Inserisci l'Occupazione</b>",
            kb_wizard_back(BTN_BACK_TO_2),
        )
        await save_session(db, s)
        await q.answer()

    elif data == BTN_REDO_DATA:
        s["view"] = "W_NICK"
        await ui_edit_or_send(
            context.bot, chat_id, s,
            "🔄 <b>Ricominciamo!</b>\n\n1️⃣ <b>Inserisci il Nickname</b>",
            kb_wizard_back(BTN_BACK_TO_START),
        )
        await save_session(db, s)
        await q.answer()

    # ── Broadcast: conferma/annulla ────────────────────────────────────────────
    elif data == BTN_BROADCAST_CONFIRM_DATA:
        if perm and perm:
            await execute_broadcast(context.bot, db, chat_id, s)
        await q.answer()

    elif data == BTN_BROADCAST_CANCEL_DATA:
        s["broadcast_text"] = None
        await save_session(db, s)
        await show_main(context.bot, db, chat_id, s)
        await q.answer()

    else:
        await q.answer()
