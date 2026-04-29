"""
Configurazione centralizzata del Bot.
Modifica questo file per personalizzare il comportamento del bot.
"""

import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── CREDENZIALI ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── INFRASTRUTTURA ────────────────────────────────────────────────────────────
DB_FILE: str = "bot.sqlite"
LOGO_PATH: str = "logo.png"          # logo fornito dall'utente (PNG)

# ── CANALE & GRUPPO ───────────────────────────────────────────────────────────
CHANNEL_ID: str = "@ProgressoRiformistaZero"   # iscrizione obbligatoria
TARGET_GROUP_ID: int = -1003825574994        # gruppo per report automatici

# ── FUSO ORARIO ───────────────────────────────────────────────────────────────
ITALY_TZ = timezone(timedelta(hours=1))

# ── PAGINAZIONE ───────────────────────────────────────────────────────────────
PAGE_SIZE_LIST: int = 25
LEADERBOARD_PAGE_SIZE: int = 10
REPORT_PAGE_SIZE: int = 3

# ── LIVELLI PERMESSO ─────────────────────────────────────────────────────────
PERM_BASE: int = 1
PERM_SCHEDA: int = 2
PERM_ADMIN: int = 3
PERM_GOD: int = 4

# ── TESTI ─────────────────────────────────────────────────────────────────────
TXT_WELCOME = (
    "<b>📢 Reparto Propaganda di Progresso Riformista</b>\n\n"
    "Benvenuto nel sistema di gestione tesserati.\n"
    "<i>Per consultare la lista dei comandi disponibili, premi il pulsante guida o digita /guida.</i>"
)
TXT_NOT_ADMIN = (
    "<b>🚫 Accesso Negato</b>\n\n"
    "Non risulti essere un amministratore autorizzato all'uso di questo Bot.\n"
    "<i>Contatta un superiore per richiedere l'accesso.</i>"
)
TXT_NOW_ADMIN = (
    "<b>✅ Autenticazione Riuscita!</b>\n\n"
    "I tuoi permessi sono stati aggiornati. Ora hai accesso alle funzionalità del Bot."
)
TXT_AUTH_PROPAGANDA = (
    "📢 <b>Reparto Propaganda di Progresso Riformista</b>\n\n"
    "✅ <b>Sei stato autorizzato all'uso del Gestionale!</b>\n"
    "Livello autorizzazione: "
)

# ── VIEWS ─────────────────────────────────────────────────────────────────────
CTX_REPORT = "CTX_REPORT"
VIEW_LIST_TESSERATI = "LIST_TESSERATI"
VIEW_LIST_ADMINS = "LIST_ADMINS"
VIEW_LEADERBOARD_HOURS = "LEADERBOARD_HOURS"
VIEW_LEADERBOARD_ADMINS = "LEADERBOARD_ADMINS"
VIEW_REPORT = "VIEW_REPORT"
VIEW_SCHEDA = "RESULT"

# ── PULSANTI ──────────────────────────────────────────────────────────────────
BTN_START_AUTH_LABEL = "📖 Inizia"
BTN_START_AUTH_DATA = "start_from_auth"
BTN_RECHECK_LABEL = "🔄 Verifica Permessi"
BTN_RECHECK_DATA = "check_admin"
BTN_REGISTER_LABEL = "📝 Registra Nuovo Tesserato"
BTN_REGISTER_DATA = "reg_begin"
BTN_GUIDE_LABEL = "📜 Guida Comandi"
BTN_GUIDE_DATA = "cmd_guide"
BTN_BACK_MAIN_LABEL = "🏠 Home"
BTN_BACK_MAIN_DATA = "back_main"
BTN_BACK_REPORT_LABEL = "🔙 Torna al Report"
BTN_BACK_REPORT_DATA = "back_to_report"
BTN_PREV_LABEL = "⬅️ Precedente"
BTN_PREV_DATA = "page_prev"
BTN_NEXT_LABEL = "Successivo ➡️"
BTN_NEXT_DATA = "page_next"
BTN_NOOP_DATA = "page_noop"
BTN_BACK_LABEL = "🔙 Indietro"
BTN_BACK_TO_START = "reg_back_start"
BTN_BACK_TO_1 = "reg_back_1"
BTN_BACK_TO_2 = "reg_back_2"
BTN_BACK_TO_3 = "reg_back_3"
BTN_SEND_LABEL = "✅ Conferma e Invia"
BTN_SEND_DATA = "reg_send"
BTN_REDO_LABEL = "❌ Annulla / Rifai"
BTN_REDO_DATA = "reg_redo"
BTN_BROADCAST_CONFIRM_DATA = "broadcast_confirm"
BTN_BROADCAST_CANCEL_DATA = "broadcast_cancel"
