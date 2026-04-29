# Bot Telegram — Reparto Propaganda di Pactum Patriae

## Struttura del progetto

```
propaganda_bot/
├── main.py                 # Entry point
├── config.py               # Tutta la configurazione (token, canali, testi, costanti)
├── requirements.txt
├── .env.example
├── logo.png                # Logo del bot (sostituisce logo.jpeg originale)
├── core/
│   ├── database.py         # Init DB, sessioni, permessi, user index
│   ├── views.py            # Rendering di tutte le viste (scheda, report, classifiche...)
│   └── scheduler.py        # Report settimanale automatico (Martedì 16:00)
├── handlers/
│   ├── messages.py         # Handler messaggi e comandi
│   ├── callbacks.py        # Handler callback query (bottoni inline)
│   └── admin.py            # Comandi admin: permesso, del_admin, del_tesserato, broadcast
└── utils/
    ├── helpers.py          # Date, normalize_query (case-insensitive), resolve_user
    ├── ui.py               # Tastiere, ui_edit_or_send, cache logo
    └── subscription.py     # Verifica iscrizione canale obbligatorio
```

---

## Setup

### 1. Installa le dipendenze

```bash
cd propaganda_bot
pip install -r requirements.txt
```

### 2. Configura il file .env

```bash
cp .env.example .env

```

### 3. Metti il logo nella cartella corretta

Il file `logo.png` deve trovarsi nella stessa cartella di `main.py`.

### 4. Avvia il bot

```bash
python main.py
```

---

## Modifiche rispetto alla versione precedente

| Modifica | Dettaglio |
|---|---|
| **Logo** | Sostituito `logo.jpeg` con il PNG fornito (`logo.png`) |
| **Canale obbligatorio** | Cambiato in `@ProgressoRiformistaZero` |
| **`/votanti` rimosso** | Eliminato comando e relativa view |
| **`/scheda` case-insensitive** | Ora cerca nick e username indipendentemente da maiuscole/minuscole |
| **`/rimuovi_admin` → `/del_admin`** | Rinominato |
| **`/elimina_tesserato` → `/del_tesserato`** | Rinominato |
| **`/broadcast`** | Nuovo comando con anteprima e conferma prima dell'invio |
| **Struttura modulare** | Codice diviso in moduli separati per manutenibilità |
| **Fix sicurezza** | Validazione ore (no valori negativi), escape HTML ovunque, controllo permessi più granulare |

---

## Comandi disponibili

### Tutti gli utenti autorizzati (Livello 1+)
- `/start` — Avvia il bot / torna alla home
- `/guida` — Mostra la guida ai comandi

### Livello 2+
- `/scheda @user [...]` — Cerca scheda tesserato (case-insensitive)

### Livello 3+
- `/classifica_ore` — Classifica per ore
- `/classifica_admin` — Classifica admin per produttività
- `/lista_tesserati` — Lista completa tesserati
- `/lista_admin` — Lista amministratori
- `/report [dd/mm/yyyy]` — Report settimanale
- `/broadcast Testo...` — Broadcast interno (con anteprima)
- `/permesso @username [1|2|3]` — Imposta permessi
- `/aggiungi_admin @username [livello]` — Aggiunge admin
- `/del_admin @username` — Rimuove admin
- `/del_tesserato ID|@user|nick` — Elimina tesserato

### Livello 4 (DIO)
- Può modificare/rimuovere anche i Livello 3
- Può nominare altri Livello 4

---

## Abilitare il bot in un gruppo Telegram (per test)

### Passo 1 — Aggiungi il bot al gruppo
1. Apri il gruppo Telegram dove vuoi testare il bot
2. Clicca sul nome del gruppo → **Aggiungi membro**
3. Cerca il tuo bot per username e aggiungilo

### Passo 2 — Rendi il bot amministratore del gruppo
Per poter ricevere tutti i messaggi e pinnare i report automatici, il bot deve essere **amministratore**:
1. Vai nelle impostazioni del gruppo
2. **Amministratori** → **Aggiungi amministratore** → seleziona il bot
3. Abilita almeno:
   - ✅ Elimina messaggi
   - ✅ Fissa messaggi (necessario per il report automatico)
   - ✅ Invita utenti (opzionale)

### Passo 3 — Ottieni il GROUP_ID corretto
Il `TARGET_GROUP_ID` in `config.py` deve corrispondere al tuo gruppo di test.
Per trovarlo:
1. Aggiungi temporaneamente `@userinfobot` al gruppo
2. Digita `/start` nel gruppo — ti restituirà l'ID (un numero negativo come `-1001234567890`)
3. Aggiorna `TARGET_GROUP_ID` in `config.py` con il nuovo ID
4. Rimuovi `@userinfobot` dal gruppo

### Passo 4 — Verifica con `/report`
Avvia il bot in privato, usa `/report` e verifica che il messaggio arrivi correttamente nel gruppo.

> **Nota:** Se il gruppo ha i **Topic** abilitati, il report automatico viene inviato nel topic generale (ID 0).
> Per inviarlo in un topic specifico, aggiungi il parametro `message_thread_id=<ID_TOPIC>` alla chiamata `bot.send_photo` in `core/scheduler.py`.

---

## Note di sicurezza

- I token non vengono mai loggati
- L'HTML user-generated è sempre escaped con `html.escape()`
- Le ore del tesserato non possono essere negative
- I permessi Livello 4 non sono modificabili da nessuno tranne da un altro Livello 4
- Il broadcast è disponibile solo da Livello 3+
- La conferma broadcast richiede doppia azione (anteprima + conferma)
