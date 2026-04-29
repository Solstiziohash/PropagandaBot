"""
Componenti UI: tastiere inline e funzione di invio/modifica messaggi.
"""

import logging
from typing import Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import (
    LOGO_PATH,
    BTN_BACK_MAIN_LABEL, BTN_BACK_MAIN_DATA,
    BTN_BACK_REPORT_LABEL, BTN_BACK_REPORT_DATA,
    BTN_GUIDE_LABEL, BTN_GUIDE_DATA,
    BTN_NOOP_DATA,
    BTN_NEXT_LABEL, BTN_NEXT_DATA,
    BTN_PREV_LABEL, BTN_PREV_DATA,
    BTN_RECHECK_LABEL, BTN_RECHECK_DATA,
    BTN_REGISTER_LABEL, BTN_REGISTER_DATA,
    BTN_SEND_LABEL, BTN_SEND_DATA,
    BTN_REDO_LABEL, BTN_REDO_DATA,
    BTN_BACK_LABEL,
    BTN_BROADCAST_CONFIRM_DATA, BTN_BROADCAST_CANCEL_DATA,
)

logger = logging.getLogger(__name__)

_CACHED_LOGO_ID: Optional[str] = None


def get_cached_logo() -> Optional[str]:
    return _CACHED_LOGO_ID


def set_cached_logo(file_id: str) -> None:
    global _CACHED_LOGO_ID
    _CACHED_LOGO_ID = file_id


def kb_empty() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([])


def kb_not_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_RECHECK_LABEL, callback_data=BTN_RECHECK_DATA)]
    ])


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_REGISTER_LABEL, callback_data=BTN_REGISTER_DATA)],
        [InlineKeyboardButton(BTN_GUIDE_LABEL, callback_data=BTN_GUIDE_DATA)],
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK_MAIN_LABEL, callback_data=BTN_BACK_MAIN_DATA)]
    ])


def kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(BTN_SEND_LABEL, callback_data=BTN_SEND_DATA),
        InlineKeyboardButton(BTN_REDO_LABEL, callback_data=BTN_REDO_DATA),
    ]])


def kb_broadcast_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Invia a tutti", callback_data=BTN_BROADCAST_CONFIRM_DATA),
        InlineKeyboardButton("❌ Annulla", callback_data=BTN_BROADCAST_CANCEL_DATA),
    ]])


def kb_pagination(
    current: int, total: int, back_report: bool = False
) -> InlineKeyboardMarkup:
    rows = []
    if total > 1:
        row_nav = []
        if current > 0:
            row_nav.append(
                InlineKeyboardButton(BTN_PREV_LABEL, callback_data=BTN_PREV_DATA)
            )
        row_nav.append(
            InlineKeyboardButton(
                f"📄 {current + 1} / {total}", callback_data=BTN_NOOP_DATA
            )
        )
        if current < total - 1:
            row_nav.append(
                InlineKeyboardButton(BTN_NEXT_LABEL, callback_data=BTN_NEXT_DATA)
            )
        rows.append(row_nav)
    back_label = BTN_BACK_REPORT_LABEL if back_report else BTN_BACK_MAIN_LABEL
    back_data = BTN_BACK_REPORT_DATA if back_report else BTN_BACK_MAIN_DATA
    rows.append([InlineKeyboardButton(back_label, callback_data=back_data)])
    return InlineKeyboardMarkup(rows)


def kb_wizard_back(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK_LABEL, callback_data=step)]
    ])


async def ui_edit_or_send(
    bot: Bot,
    chat_id: int,
    s: dict,
    caption: str,
    markup: InlineKeyboardMarkup,
) -> None:
    if s["bot_msg_id"] != 0:
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=s["bot_msg_id"],
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
            return
        except BadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return
            # Messaggio non più disponibile, lo resettiamo
            s["bot_msg_id"] = 0

    # Nuovo invio con foto
    photo = get_cached_logo() or open(LOGO_PATH, "rb")
    msg = await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=markup,
        parse_mode=ParseMode.HTML,
    )
    if not get_cached_logo() and msg.photo:
        set_cached_logo(msg.photo[-1].file_id)

    s["bot_msg_id"] = msg.message_id