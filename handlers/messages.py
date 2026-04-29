"""
Handler per tutti i messaggi in arrivo (comandi e testo libero nel wizard).
"""

import html
import logging, asyncio
from typing import Optional

import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from config import (
    CTX_REPORT, VIEW_REPORT, VIEW_SCHEDA,
    VIEW_LEADERBOARD_HOURS, VIEW_LEADERBOARD_ADMINS,
    VIEW_LIST_ADMINS, VIEW_LIST_TESSERATI,
    BTN_BACK_TO_START, BTN_BACK_TO_1, BTN_BACK_TO_2, BTN_BACK_TO_3,
)
from core.database import get_admin_perm, load_session, save_session, index_user
from core.views import (
    show_main, show_guide,
    render_scheda_page, render_report_page,
    render_leaderboard_hours, render_list_generic,
)
from handlers.admin import (
    handle_perm_command, handle_del_admin, handle_del_tesserato,
    handle_broadcast_command,
)
from utils.helpers import normalize_query
from utils.subscription import check_subscription, send_subscription_barrier
from utils.ui import ui_edit_or_send, kb_not_admin, kb_back_main, kb_wizard_back, kb_confirm

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: aiosqlite.Connection = context.bot_data["db"]
    msg = update.message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    chat_id = msg.chat_id
    text = (msg.text or "").strip()
    is_private = msg.chat.type == "private"

    await index_user(db, user)

    # Cancella il messaggio dell'utente in privato (non su /start)
    if is_private:
        if text.startswith("/start"):
            # Cancella /start dopo 2 secondi così l'utente lo vede sparire
            async def _delete_later():
                import asyncio
                await asyncio.sleep(2)
                try:
                    await context.bot.delete_message(chat_id, msg.message_id)
                except Exception:
                    pass
            asyncio.create_task(_delete_later())
        else:
            try:
                await context.bot.delete_message(chat_id, msg.message_id)
            except Exception:
                pass

    # ── Gestione comandi ───────────────────────────────────────────────────────
    if text.startswith("/"):
        parts = text.split(None, 1)
        cmd_raw = parts[0].lstrip("/").split("@")[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        perm = await get_admin_perm(db, user.id)
        lvl = perm or 0

        if cmd_raw == "start":
            # Cancella eventuale messaggio di sistema precedente
            async with db.execute(
                "SELECT msg_id FROM user_system_msgs WHERE user_id=?", (user.id,)
            ) as cur:
                row = await cur.fetchone()
            if row and row["msg_id"] and is_private:
                try:
                    await context.bot.delete_message(chat_id, row["msg_id"])
                except Exception:
                    pass
                await db.execute(
                    "DELETE FROM user_system_msgs WHERE user_id=?", (user.id,)
                )
                await db.commit()

            if not await check_subscription(context.bot, user.id):
                return await send_subscription_barrier(context.bot, chat_id)

            # Azzera bot_msg_id nel DB e nella sessione locale
            await db.execute(
                "UPDATE sessions SET bot_msg_id = 0 WHERE chat_id = ?", (chat_id,)
            )
            await db.commit()

            # Carica sessione fresca con bot_msg_id = 0
            s = await load_session(db, chat_id)
            s["bot_msg_id"] = 0

            if lvl > 0:
                await show_main(context.bot, db, chat_id, s)
            else:
                await ui_edit_or_send(
                    context.bot, chat_id, s,
                    "<b>🚫 Accesso Negato</b>\n\n"
                    "Non risulti essere un amministratore autorizzato.\n"
                    "<i>Contatta un superiore per richiedere l'accesso.</i>",
                    kb_not_admin(),
                )
                await save_session(db, s)
            return

        # Per tutti gli altri comandi, verifica iscrizione e carica sessione
        if not await check_subscription(context.bot, user.id):
            return await send_subscription_barrier(context.bot, chat_id)

        s = await load_session(db, chat_id)

        if perm is None:
            s["view"] = "NOT_ADMIN"
            await ui_edit_or_send(
                context.bot, chat_id, s,
                "<b>🚫 Accesso Negato</b>\n\n"
                "Non risulti essere un amministratore autorizzato.\n"
                "<i>Contatta un superiore per richiedere l'accesso.</i>",
                kb_not_admin(),
            )
            await save_session(db, s)
            return

        if cmd_raw == "guida":
            await show_guide(context.bot, db, chat_id, s, lvl)

        elif cmd_raw == "scheda":
            if lvl < 2:
                return await ui_edit_or_send(
                    context.bot, chat_id, s,
                    "<b>🚫 Permessi insufficienti.</b>",
                    kb_back_main(),
                )
            cl = args.replace(",", " ").strip()
            if not cl:
                return await ui_edit_or_send(
                    context.bot, chat_id, s,
                    "ℹ️ <b>Uso:</b> /scheda @user ...",
                    kb_back_main(),
                )
            if s["view"] == VIEW_REPORT:
                s["occupation"] = CTX_REPORT
                s["hours"] = s["search_index"]
            else:
                s["occupation"] = None
            s["search_query"] = cl
            s["search_index"] = 0
            await save_session(db, s)
            await render_scheda_page(context.bot, db, chat_id, s)

        elif cmd_raw == "classifica_ore" and lvl >= 3:
            s.update({"view": VIEW_LEADERBOARD_HOURS, "search_index": 0})
            await save_session(db, s)
            await render_leaderboard_hours(context.bot, db, chat_id, s)

        elif cmd_raw == "classifica_admin" and lvl >= 3:
            s.update({"view": VIEW_LEADERBOARD_ADMINS, "search_index": 0})
            await save_session(db, s)
            await render_list_generic(context.bot, db, chat_id, s)

        elif cmd_raw == "lista_tesserati" and lvl >= 3:
            s.update({"view": VIEW_LIST_TESSERATI, "search_index": 0})
            await save_session(db, s)
            await render_list_generic(context.bot, db, chat_id, s)

        elif cmd_raw == "lista_admin" and lvl >= 3:
            s.update({"view": VIEW_LIST_ADMINS, "search_index": 0})
            await save_session(db, s)
            await render_list_generic(context.bot, db, chat_id, s)

        elif cmd_raw == "report" and lvl >= 3:
            s["search_index"] = 0
            s["occupation"] = f"REPORT:{args.strip()}" if args.strip() else "REPORT"
            await save_session(db, s)
            await render_report_page(context.bot, db, chat_id, s)

        elif cmd_raw in ("permesso", "aggiungi_admin") and lvl >= 3:
            reply_uid = _extract_reply_uid(msg)
            await handle_perm_command(context.bot, db, chat_id, s, lvl, args, reply_uid)

        elif cmd_raw == "del_admin" and lvl >= 3:
            reply_uid = _extract_reply_uid(msg)
            await handle_del_admin(context.bot, db, chat_id, s, lvl, args, reply_uid)

        elif cmd_raw == "del_tesserato" and lvl >= 3:
            await handle_del_tesserato(context.bot, db, chat_id, s, args)

        elif cmd_raw == "broadcast" and lvl >= 4:
            await handle_broadcast_command(context.bot, db, chat_id, s, args)

        return

    # ── Testo libero: verifica iscrizione e carica sessione ───────────────────
    if not await check_subscription(context.bot, user.id):
        return await send_subscription_barrier(context.bot, chat_id)

    s = await load_session(db, chat_id)

    # ── Wizard di registrazione ────────────────────────────────────────────────
    if s["view"] in ("W_NICK", "W_USER", "W_OCC", "W_HOURS", "CONFIRM"):
        if s["view"] == "W_NICK" and text:
            s["nick"] = text
            s["view"] = "W_USER"
            await ui_edit_or_send(
                context.bot, chat_id, s,
                "2️⃣ <b>Inserisci l'Username Telegram</b>\n"
                "(es. @utente; se non disponibile scrivi <code>Nessuno</code>)",
                kb_wizard_back(BTN_BACK_TO_1),
            )

        elif s["view"] == "W_USER" and text:
            username = normalize_query(text)[0]
            async with db.execute(
                "SELECT id, nick FROM tesserati WHERE LOWER(username) = LOWER(?)",
                (username,),
            ) as cur:
                existing = await cur.fetchone()
            if existing:
                await ui_edit_or_send(
                    context.bot, chat_id, s,
                    f"⚠️ <b>Username già tesserato!</b>\n\n"
                    f"Esiste già un profilo con questo username.\n"
                    f"ID: <b>#{existing['id']}</b> — <b>{html.escape(existing['nick'])}</b>\n\n"
                    f"Usa /scheda per visualizzarlo.",
                    kb_back_main(),
                )
                await save_session(db, s)
                return
            s["username"] = username
            s["view"] = "W_OCC"
            await ui_edit_or_send(
                context.bot, chat_id, s,
                "3️⃣ <b>Inserisci l'Occupazione</b>\n(la Pex)",
                kb_wizard_back(BTN_BACK_TO_2),
            )

        elif s["view"] == "W_OCC" and text:
            s["occupation"] = text
            s["view"] = "W_HOURS"
            await ui_edit_or_send(
                context.bot, chat_id, s,
                "4️⃣ <b>Inserisci le Ore Totali</b>\n"
                "(Digita <b>solo</b> il numero intero, es: 120)",
                kb_wizard_back(BTN_BACK_TO_3),
            )

        elif s["view"] == "W_HOURS":
            try:
                h = int(text)
                if h < 0:
                    raise ValueError("negative hours")
                s["hours"] = h
                s["view"] = "CONFIRM"
                recap = (
                    f"📝 <b>Riepilogo Dati</b>\n"
                    f"Controlla attentamente prima di confermare.\n\n"
                    f"👤 <b>Nick:</b> {_esc(s['nick'])}\n"
                    f"🏷️ <b>User:</b> {_esc(s['username'])}\n"
                    f"🛠️ <b>Ruolo:</b> {_esc(s['occupation'])}\n"
                    f"⏱️ <b>Ore:</b> {h}"
                )
                await ui_edit_or_send(context.bot, chat_id, s, recap, kb_confirm())
            except ValueError:
                await ui_edit_or_send(
                    context.bot, chat_id, s,
                    "⚠️ <b>Formato non valido.</b>\n"
                    "Inserisci un numero intero positivo per le ore (es. 100).",
                    kb_wizard_back(BTN_BACK_TO_3),
                )

        await save_session(db, s)


def _extract_reply_uid(msg) -> Optional[int]:
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    return None


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""