"""
Gestione verifica iscrizione al canale obbligatorio.
"""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import CHANNEL_ID


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Verifica se l'utente è iscritto al canale obbligatorio."""
    try:
        from telegram import ChatMemberLeft, ChatMemberBanned
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return not isinstance(member, (ChatMemberLeft, ChatMemberBanned))
    except TelegramError:
        return False


async def send_subscription_barrier(bot: Bot, chat_id: int) -> None:
    """Invia il messaggio di richiesta iscrizione al canale."""
    channel_link = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Iscriviti", url=channel_link)],
        [InlineKeyboardButton(
            "🔄 Ho effettuato l'iscrizione", callback_data="check_sub"
        )],
    ])
    await bot.send_message(
        chat_id,
        (
            "✖️ <b>Per utilizzare il Bot devi essere iscritto al Canale del partito!</b>\n\n"
            f"Canale: {channel_link}"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
