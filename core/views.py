"""
Funzioni di rendering per tutte le viste del bot.
"""

import html
import logging
from datetime import datetime, timezone

import aiosqlite
from telegram import Bot

from config import (
    ITALY_TZ,
    CTX_REPORT,
    VIEW_SCHEDA, VIEW_REPORT,
    VIEW_LEADERBOARD_HOURS, VIEW_LEADERBOARD_ADMINS,
    VIEW_LIST_ADMINS, VIEW_LIST_TESSERATI,
    LEADERBOARD_PAGE_SIZE, PAGE_SIZE_LIST, REPORT_PAGE_SIZE,
    TXT_WELCOME,
    BTN_BACK_TO_START, BTN_BACK_TO_1, BTN_BACK_TO_2, BTN_BACK_TO_3,
)
from utils.helpers import (
    get_week_start, get_week_end,
    format_datetime_for_sql, parse_date_ddmmyyyy, normalize_query,
)
from utils.ui import (
    ui_edit_or_send,
    kb_main, kb_back_main, kb_pagination, kb_wizard_back,
)
from core.database import save_session, get_admin_perm

logger = logging.getLogger(__name__)


# ─── HOME ─────────────────────────────────────────────────────────────────────

async def show_main(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    s.update({
        "view": "MAIN",
        "nick": None, "username": None,
        "occupation": None, "hours": None,
        "search_query": None, "search_index": 0,
        "admin_id": None, "broadcast_text": None,
    })
    await ui_edit_or_send(bot, chat_id, s, TXT_WELCOME, kb_main())
    await save_session(db, s)


# ─── GUIDA ────────────────────────────────────────────────────────────────────

async def show_guide(
    bot: Bot, db: aiosqlite.Connection,
    chat_id: int, s: dict, perm: int,
) -> None:
    s["view"] = "GUIDE"
    out = "<b>📚 Guida ai Comandi</b>\n\n"
    out += (
        "🔹 <b>Registrazione:</b> "
        "Premi <i>Registra Nuovo Tesserato</i> nel menu principale.\n\n"
    )
    if perm >= 2:
        out += (
            "🔹 <b>Ricerca Tesserato:</b>\n"
            "<code>/scheda @user1 @user2 ID ...</code>\n"
            "(Cerca uno o più utenti per nick, @ o ID).\n\n"
        )
    if perm >= 3:
        out += (
            "<b>👑 Comandi Admin:</b>\n"
            "• 🏆 <code>/classifica_ore</code>\n"
            "• 🎖️ <code>/classifica_admin</code>\n"
            "• 👥 <code>/lista_tesserati</code>\n"
            "• 👮 <code>/lista_admin</code>\n"
            "• 📊 <code>/report</code> — Report settimana corrente\n"
            "• 📊 <code>/report dd/mm/yyyy</code> — Report settimana specifica\n"
            "• 📣 <code>/broadcast Testo...</code> — Broadcast interno\n\n"
            "<b>⚙️ Gestione Permessi:</b>\n"
            "• <code>/permesso @username 1|2|3</code> (Liv 4 per creare Admin)\n"
            "• <code>/aggiungi_admin @username [livello]</code>\n"
            "• <code>/del_admin @username</code>\n"
            "• <code>/del_tesserato ID|@user|nick</code>\n"
        )
    if perm >= 4:
        out += "\n⚡ <b>Livello 4 (DIO):</b>\nTu puoi fare quello che vuoi."
    await ui_edit_or_send(bot, chat_id, s, out, kb_back_main())
    await save_session(db, s)


# ─── SCHEDA ───────────────────────────────────────────────────────────────────

async def render_scheda_page(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    s["view"] = VIEW_SCHEDA
    query_str = s.get("search_query") or ""
    inputs = query_str.split()
    total = len(inputs)
    back_report = s.get("occupation") == CTX_REPORT

    if total == 0:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "⚠️ <b>Nessun dato da visualizzare.</b>",
            kb_back_main(),
        )

    s["search_index"] = max(0, min(s["search_index"], total - 1))
    u, n, id_val = normalize_query(inputs[s["search_index"]])

    # Ricerca case-insensitive: LOWER() su entrambi i lati
    async with db.execute(
        """SELECT t.id, t.nick, t.username, t.occupation, t.hours,
                  t.admin_id, t.created_at,
                  u.last_username, u.first_name
           FROM tesserati t
           LEFT JOIN user_index u ON t.admin_id = u.user_id
           WHERE LOWER(t.username) = ? OR LOWER(t.nick) = ? OR t.id = ?
           LIMIT 1""",
        (u, n, id_val),
    ) as cur:
        row = await cur.fetchone()

    if row:
        admin_label = (
            row["last_username"] or row["first_name"] or f"id {row['admin_id']}"
        )
        txt = (
            f"<b>📂 Fascicolo Tesserato ({s['search_index']+1}/{total})</b>\n\n"
            f"🆔 <b>ID:</b> {row['id']}\n"
            f"👤 <b>Nick:</b> {html.escape(row['nick'])}\n"
            f"🏷️ <b>Username:</b> {html.escape(row['username'])}\n"
            f"🛠️ <b>Occupazione:</b> {html.escape(row['occupation'])}\n"
            f"⏱️ <b>Ore totali:</b> {row['hours']}\n"
            f"📅 <b>Registrato il:</b> {html.escape(row['created_at'])}\n"
            f"👮 <b>Tesserato da:</b> {html.escape(admin_label)}"
        )
    else:
        txt = (
            f"<b>🚫 Fascicolo non trovato ({s['search_index']+1}/{total})</b>\n\n"
            f"Nessuna corrispondenza per: "
            f"<b>{html.escape(inputs[s['search_index']])}</b>."
        )

    await ui_edit_or_send(
        bot, chat_id, s, txt,
        kb_pagination(s["search_index"], total, back_report),
    )


# ─── REPORT ───────────────────────────────────────────────────────────────────

async def render_report_page(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    s["view"] = VIEW_REPORT
    now = datetime.now(timezone.utc)
    occupation = s.get("occupation") or ""

    if occupation.startswith("REPORT:"):
        date_str = occupation[len("REPORT:"):]
        parsed = parse_date_ddmmyyyy(date_str)
        week_start = (
            get_week_start(parsed.astimezone(timezone.utc))
            if parsed else get_week_start(now)
        )
    else:
        week_start = get_week_start(now)

    week_end = get_week_end(week_start)
    start_str = format_datetime_for_sql(week_start)
    end_str = format_datetime_for_sql(week_end)

    async with db.execute(
        "SELECT COUNT(DISTINCT admin_id) FROM tesserati "
        "WHERE created_at >= ? AND created_at < ?",
        (start_str, end_str),
    ) as cur:
        count = (await cur.fetchone())[0]

    start_italy = week_start.astimezone(ITALY_TZ)
    end_italy = week_end.astimezone(ITALY_TZ)
    period_fmt = (
        f"{start_italy.strftime('%d/%m/%Y %H:%M')} — "
        f"{end_italy.strftime('%d/%m/%Y %H:%M')}"
    )

    if count == 0:
        return await ui_edit_or_send(
            bot, chat_id, s,
            f"📅 <b>Report Settimanale</b>\n"
            f"<b>Periodo:</b> {period_fmt}\n\n"
            f"<i>Nessuna registrazione effettuata in questo periodo.</i>",
            kb_back_main(),
        )

    total_pages = (count + REPORT_PAGE_SIZE - 1) // REPORT_PAGE_SIZE
    s["search_index"] = max(0, min(s["search_index"], total_pages - 1))
    offset = s["search_index"] * REPORT_PAGE_SIZE

    async with db.execute(
        """SELECT t.admin_id, COUNT(*) as recent_count,
                  GROUP_CONCAT(t.nick, '|') as nick_list,
                  u.last_username, u.first_name
           FROM tesserati t
           LEFT JOIN user_index u ON t.admin_id = u.user_id
           WHERE t.created_at >= ? AND t.created_at < ?
           GROUP BY t.admin_id
           ORDER BY recent_count DESC
           LIMIT ? OFFSET ?""",
        (start_str, end_str, REPORT_PAGE_SIZE, offset),
    ) as cur:
        rows = await cur.fetchall()

    async with db.execute(
        "SELECT COUNT(*) FROM tesserati WHERE created_at >= ? AND created_at < ?",
        (start_str, end_str),
    ) as cur:
        total_week = (await cur.fetchone())[0]

    out = f"<b>📊 Report Settimanale</b>\n<b>Periodo:</b> {period_fmt}\n"
    if total_pages > 1:
        out += f"<i>Pagina {s['search_index']+1}/{total_pages}</i>\n"
    out += "\n"

    for idx, row in enumerate(rows):
        label = row["last_username"] or row["first_name"] or f"id {row['admin_id']}"
        nicks_fmt = ", ".join(
            f"<code>{html.escape(n)}</code>"
            for n in (row["nick_list"] or "").split("|")
        )
        out += (
            f"<b>{offset + idx + 1}.</b> {html.escape(label)} — "
            f"<b>+{row['recent_count']}</b> nuovi\n{nicks_fmt}\n\n"
        )
    out += f"📈 <b>Totale registrazioni periodo:</b> {total_week}"

    await ui_edit_or_send(
        bot, chat_id, s, out,
        kb_pagination(s["search_index"], total_pages),
    )


# ─── CLASSIFICA ORE ───────────────────────────────────────────────────────────

async def render_leaderboard_hours(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    s["view"] = VIEW_LEADERBOARD_HOURS
    async with db.execute("SELECT COUNT(*) FROM tesserati") as cur:
        total_items = (await cur.fetchone())[0]

    if total_items == 0:
        return await ui_edit_or_send(
            bot, chat_id, s,
            "<b>🏆 Classifica Ore</b>\n\n<i>Nessun tesserato registrato.</i>",
            kb_back_main(),
        )

    total_pages = (total_items + LEADERBOARD_PAGE_SIZE - 1) // LEADERBOARD_PAGE_SIZE
    s["search_index"] = max(0, min(s["search_index"], total_pages - 1))
    offset = s["search_index"] * LEADERBOARD_PAGE_SIZE

    async with db.execute(
        """SELECT t.nick, t.username, t.hours, t.admin_id,
                  u.last_username, u.first_name
           FROM tesserati t
           LEFT JOIN user_index u ON t.admin_id = u.user_id
           ORDER BY t.hours DESC LIMIT ? OFFSET ?""",
        (LEADERBOARD_PAGE_SIZE, offset),
    ) as cur:
        rows = await cur.fetchall()

    out = "<b>🏆 Classifica Ore</b>\n"
    if total_pages > 1:
        out += f"<i>Pagina {s['search_index']+1}/{total_pages}</i>\n"
    out += "\n"

    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for idx, row in enumerate(rows):
        admin_label = (
            row["last_username"] or row["first_name"] or f"id {row['admin_id']}"
        )
        medal = medals.get(offset + idx, "▪️")
        out += (
            f"{medal} <b>{html.escape(row['nick'])}</b> "
            f"({html.escape(row['username'])})\n"
            f"   ⏱️ <b>{row['hours']}h</b> — 👮 {html.escape(admin_label)}\n\n"
        )

    await ui_edit_or_send(
        bot, chat_id, s, out,
        kb_pagination(s["search_index"], total_pages),
    )


# ─── LISTE GENERICHE ──────────────────────────────────────────────────────────

async def render_list_generic(
    bot: Bot, db: aiosqlite.Connection, chat_id: int, s: dict
) -> None:
    view = s["view"]
    config = {
        VIEW_LIST_TESSERATI: (
            "SELECT COUNT(*) FROM tesserati",
            "SELECT id, nick, username, hours FROM tesserati "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            PAGE_SIZE_LIST,
        ),
        VIEW_LIST_ADMINS: (
            "SELECT COUNT(*) FROM admins",
            "SELECT user_id, perm_level, tesserati_count FROM admins "
            "ORDER BY perm_level DESC, tesserati_count DESC LIMIT ? OFFSET ?",
            PAGE_SIZE_LIST,
        ),
        VIEW_LEADERBOARD_ADMINS: (
            "SELECT COUNT(*) FROM admins",
            "SELECT user_id, perm_level, tesserati_count FROM admins "
            "ORDER BY tesserati_count DESC LIMIT ? OFFSET ?",
            LEADERBOARD_PAGE_SIZE,
        ),
    }
    if view not in config:
        return

    count_sql, data_sql, page_size = config[view]
    async with db.execute(count_sql) as cur:
        total_items = (await cur.fetchone())[0]

    if total_items == 0:
        return await ui_edit_or_send(
            bot, chat_id, s, "📂 <b>Nessun dato.</b>", kb_back_main()
        )

    total_pages = (total_items + page_size - 1) // page_size
    s["search_index"] = max(0, min(s["search_index"], total_pages - 1))
    offset = s["search_index"] * page_size

    async with db.execute(data_sql, (page_size, offset)) as cur:
        rows = await cur.fetchall()

    out = ""
    if view == VIEW_LIST_TESSERATI:
        out = "<b>🗂️ Registro Tesserati</b>\n"
        if total_pages > 1:
            out += f"<i>Pagina {s['search_index']+1}/{total_pages} (Tot: {total_items})</i>\n"
        else:
            out += f"<i>Totale: {total_items}</i>\n"
        out += "\n"
        for row in rows:
            out += (
                f"• #{row['id']} <b>{html.escape(row['nick'])}</b> "
                f"({html.escape(row['username'])}) - {row['hours']}h\n"
            )

    elif view in (VIEW_LIST_ADMINS, VIEW_LEADERBOARD_ADMINS):
        title = (
            "<b>👮 Lista Amministratori</b>"
            if view == VIEW_LIST_ADMINS
            else "<b>👮 Classifica Produttività Admin</b>"
        )
        out = f"{title}\n"
        if total_pages > 1:
            out += f"<i>Pagina {s['search_index']+1}/{total_pages}</i>\n"
        out += "\n"
        for row in rows:
            uid = row["user_id"]
            async with db.execute(
                "SELECT last_username, first_name FROM user_index WHERE user_id=?",
                (uid,),
            ) as cur2:
                ui_row = await cur2.fetchone()
            label = (
                (ui_row["last_username"] or ui_row["first_name"]) if ui_row else None
            ) or f"id {uid}"
            out += (
                f"• <b>{html.escape(label)}</b> "
                f"(Lvl {row['perm_level']}) - Tess: {row['tesserati_count']}\n"
            )

    await ui_edit_or_send(
        bot, chat_id, s, out,
        kb_pagination(s["search_index"], total_pages),
    )
