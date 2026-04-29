# 🦁 PropagandaBot — Progresso Riformista

Bot Telegram per la gestione interna del partito.
Accesso riservato agli amministratori autorizzati.

---

## 📦 Requisiti

- Python 3.10+
- Token bot da [@BotFather](https://t.me/BotFather)
- File `.env` configurato

---

## 🚀 Avvio

```bash
pip install -r requirements.txt
python main.py
```

---

## 🛠️ Comandi

| Livello | Comandi |
|---|---|
| ⭐ 1+ | `/start` `/guida` |
| ⭐⭐ 2+ | `/scheda` |
| ⭐⭐⭐ 3+ | `/classifica_ore` `/classifica_admin` `/lista_tesserati` `/lista_admin` `/report` `/broadcast` `/permesso` `/aggiungi_admin` `/del_admin` `/del_tesserato` |
| ⭐⭐⭐⭐ 4 | Accesso completo |

---

## 📋 Changelog

- Nuova struttura modulare del codice
- Ricerca tesserati case-insensitive
- Controllo duplicati durante la registrazione
- Comando `/broadcast` con anteprima e conferma
- Report settimanale automatico nel canale
- Comandi rinominati: `/del_admin` `/del_tesserato`
- Notifica di accesso solo al primo ingresso
