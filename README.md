# FIFTEEN LEAGUE — Pubblicazione su GitHub Pages

Questo pacchetto rende l'app **completamente autonoma**: la ricerca delle carte
(nome + foto) funziona appena la pagina è online, **senza script da avviare,
senza Python sul tuo computer, senza proxy**.

## Cosa contiene

| File | A cosa serve |
|------|--------------|
| `index.html` | L'app completa (tutto in un file) — **loghi del sito e delle squadre già incorporati dentro** |
| `cards.json` | Catalogo completo: **~21.700 carte** (rating 47–95, l'intero database FutGenie) con foto carta |
| `fut_scraper.py` | Lo scraper che **GitHub** eseguirà per aggiornare il catalogo |
| `requirements.txt` | Dipendenze opzionali dello scraper (per la strategia futbin, non serve a FutGenie) |
| `.github/workflows/update-cards.yml` | L'automazione che aggiorna `cards.json` e rideploya il sito |
| `.github/workflows/apply-password.yml` | L'automazione che applica la **password di modifica** (GitHub Secrets) all'app |

## Come funziona (in 10 secondi)

- L'app, appena aperta, scarica `cards.json` **dal suo stesso sito** (stesso
  dominio → nessun problema CORS, nessun proxy).
- Le immagini delle carte arrivano dal CDN di FutGenie (`assets.futgenie.gg`).
- Un'automazione di GitHub ("Actions") rilancia lo scraper ogni lunedì e
  **aggiunge** a `cards.json` tutte le carte nuove pubblicate nel frattempo:
  il file cresce nel tempo e non perde mai carte. Puoi lanciarla anche a mano.

### Il catalogo cresce, non si rimpiazza (merge incrementale)

Ad ogni esecuzione il workflow:
1. **legge** il `cards.json` esistente e **mantiene tutte le carte** già presenti;
2. riscarica il database FutGenie fino al rating previsto e **aggiunge solo le
   carte nuove** (una carta è "la stessa" se ha stesso nome + stessa immagine:
   le diverse versioni — base, TOTW, promo — restano tutte);
3. **non può mai accorciare** il catalogo: se il nuovo merge avesse meno carte
   di prima, il job fallisce senza pubblicare nulla (controllo di sicurezza);
4. committa il file aggiornato solo se è davvero cambiato.

Il parametro **deepen** (default 20) fa scendere il catalogo di 20 rating sotto
il minimo attuale ad ogni run (mai sotto `min_overall`, default 45 = tutto il
database). Con il catalogo già completo, ogni run serve solo ad aggiungere le
novità settimanali (TOTW, promo, nuovi calciatori).

### Loghi del sito e delle squadre

I loghi sono **incorporati dentro `index.html`** (in base64): nessuna cartella
immagini da caricare, funzionano anche offline. Compariscono nell'intestazione
del sito, in classifica, nelle rose, nel tab Squadre e nel Modulo. Le squadre
**Talento lirico** e **Carisma** non hanno un logo nel pacchetto: al posto
del logo mostrano un monogramma (la loro iniziale). Per cambiare un logo o
aggiungerne dei nuovi basta far generare un nuovo `index.html`.

---

## Proteggi le modifiche con una password (GitHub Secrets)

Sì, è possibile: la password vive nei **Secret** del repository (non è mai
visibile nel codice) e un workflow ne scrive dentro `index.html` solo
**l'impronta SHA-256** (con salt). Chi non conosce la password vede il sito in
sola lettura: il pulsante "🔒 Modifica bloccata" compare in alto e ogni
modifica (giornate, esiti, rose, premi, modulo, import) chiede la password.
Sbloccata una volta, resta attiva per tutta la sessione del browser.

### Configurazione (3 minuti)
1. Nel repository: **Settings → Secrets and variables → Actions** →
   **New repository secret**.
2. Name: `EDIT_PASSWORD` — Secret: la password che vuoi (es. una frase facile
   da ricordare). **Save**.
3. Carica nel repo il file `.github/workflows/apply-password.yml` di questo
   pacchetto (Add file → Upload files, mantiene le cartelle).
4. Appena caricato (o ogni volta che modifichi `index.html`) il workflow parte
   da solo e applica l'hash. Puoi anche lanciarlo a mano:
   **Actions → Applica password di modifica → Run workflow**.

### Come funziona
- La password **non viene mai salvata** nel repo: solo il suo hash SHA-256
  (`sha256("fl-edit-v1|" + password)`), calcolato dal workflow al volo.
- Per **cambiare password**: aggiorna il secret `EDIT_PASSWORD` e rilancia il
  workflow (Run workflow) — l'hash viene sostituito.
- Se il secret non è impostato, il sito resta in modalità modifica libera
  (comodo per provare, ma pubblicamente modificabile da chiunque abbia il link).
- Copia locale (`index.html` scaricato e aperto sul tuo PC): modifica sempre
  libera, nessuna password richiesta.
- Nota onesta: la protezione è **lato client** — blocca le modifiche
  accidentali e i visitatori occasionali, ma non è una barriera crittografica
  contro un esperto (i dati, peraltro, vivono comunque solo nel browser di
  ciascun visitatore). Usa una password lunga: l'hash è pubblico nel codice.

---

## Pubblicare: guida passo-passo (solo browser, ~10 minuti)

### 1 — Account e repository
1. Entra su [github.com](https://github.com) (crea un account gratuito se non ce l'hai).
2. In alto a destra: **+** → **New repository**.
3. Repository name: `fifteen-league` (o il nome che vuoi).
4. Visibilità: **Public** (obbligatoria per GitHub Pages gratuito).
5. NON spuntare "Add a README". Clicca **Create repository**.

### 2 — Caricare i file
1. Nella pagina del repository appena creato, clicca il link
   **"uploading an existing file"** (oppure **Add file → Upload files**).
2. Trascina **index.html, cards.json, fut_scraper.py, requirements.txt, README.md**
   (tutti i file visibili di questa cartella).
3. Clicca **Commit changes**.

### 3 — Creare l'automazione (una volta sola)
1. Sempre nella pagina del repository: **Add file → Create new file**.
2. Nel campo del nome scrivi esattamente:
   `.github/workflows/update-cards.yml`
   (scrivendo le barre GitHub crea automaticamente le cartelle).
3. Incolla dentro il contenuto del file
   `.github/workflows/update-cards.yml` di questo pacchetto
   (lo trovi anche in fondo a questo README, pronto da copiare).
4. Clicca **Commit changes**.

### 4 — Attivare GitHub Pages
1. Nel repository: **Settings → Pages** (menu laterale sinistro).
2. In "Build and deployment" → Source: **Deploy from a branch**.
3. Branch: **main**, cartella: **/ (root)** → **Save**.
4. Aspetta 1–2 minuti e ricarica la pagina: troverai il link del tuo sito:
   `https://TUONOME.github.io/fifteen-league/`

Fatto. Apri il link: la ricerca carte funziona subito con l'intero catalogo.

### 5 — Aggiornare il catalogo (quando vuoi / ogni lunedì automatico)
- Manuale: nel repository → scheda **Actions** →
  **Aggiorna catalogo carte** → **Run workflow** → **Run workflow** (verde).
  In ~5–8 minuti il catalogo viene **unito** (mantenute le esistenti, aggiunte
  le nuove) e il sito si aggiorna da solo. Nel riepilogo del run vedi quante
  carte sono state aggiunte.
- Automatico: il workflow gira ogni lunedì alle 06:00 ora italiana.
- Doppi controlli di sicurezza: catalogo sotto le 200 carte O meno carte di
  prima → il job si ferma senza sovrascrivere nulla.

---

## Hai già il sito online? Aggiorna in 2 minuti (caso fifteen-league esistente)

1. **Sostituisci `index.html`** nel repo: Add file → Upload files → trascina il
   nuovo `index.html` di questo pacchetto → Commit changes.
   (Porta dentro i loghi del sito e delle squadre + il supporto password.)
2. **Sostituisci `fut_scraper.py`** nello stesso modo.
3. **Sostituisci il workflow**: apri `.github/workflows/update-cards.yml`
   nel repo → matita (pencil) → incolla il nuovo contenuto (in fondo a questo
   README) → Commit changes.
   ⚠️ Senza questo passo il lunedì successivo il catalogo tornerebbe a
   essere **rimpiazzato** con poche carte.
4. **Aggiungi il workflow della password**: Add file → Upload files →
   trascina `.github/workflows/apply-password.yml` di questo pacchetto.
   Poi imposta il secret `EDIT_PASSWORD` (sezione qui sopra) se vuoi la
   protezione: appena caricato `index.html`, il workflow applica l'hash da solo.
5. (Facoltativo ma consigliato) **Rimpiazza anche `cards.json`** con quello di
   questo pacchetto (~21.700 carte): subito il catalogo completo.
   Se lo salti, il catalogo si completa comunque da solo nel giro di 1–2 run
   grazie al merge + deepen.
6. Actions → **Aggiorna catalogo carte** → **Run workflow**: da qui in poi il
   file cresce e si aggiorna da solo.

---

## Note

- **I dati della lega (rose, giornate, classifica)** restano nel **browser**
  (localStorage del dominio). Nessun server li conserva: usa **Esporta DB**
  (menu in alto) per fare backup o spostare i dati su un altro dispositivo,
  e **Importa** per ripristinarli.
- **Il DB carte locale** (carte che aggiungi alle rose) resta tuo: il catalogo
  online è solo una vetrina di ricerca. Le carte che usi vengono copiate nel
  DB locale e restano disponibili anche offline.
- **`fut_proxy.py` non serve più**: era solo per aggirare il CORS da file
  locale. Con il sito online il catalogo arriva dalla pagina stessa.
- La ricerca "Live FutGenie" resta come extra facoltativo (utile solo se
  servisse una carta fuori catalogo), ma non è necessaria.
- Le immagini sono caricate dal CDN di FutGenie: serve una connessione internet.
- Usa il catalogo per uso personale e con richieste limitate (il workflow fa
  ~460 richieste una volta a settimana, un ritmo rispettoso).

---

## Contenuto di `.github/workflows/apply-password.yml` (da copiare per la password)

```yaml
name: Applica password di modifica

on:
  push:
    paths: ["index.html"]
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: apply-password
  cancel-in-progress: false

jobs:
  inject:
    runs-on: ubuntu-latest
    steps:
      - name: Scarica il repository
        uses: actions/checkout@v4

      - name: Calcola l'hash della password e iniettalo in index.html
        env:
          EDIT_PASSWORD: ${{ secrets.EDIT_PASSWORD }}
        run: |
          if [ -z "$EDIT_PASSWORD" ]; then
            echo "::warning::Secret EDIT_PASSWORD non impostato: index.html resta in modalita modifica libera. Imposta il secret (vedi README, sezione 'Proteggi le modifiche con una password') e rilancia questo workflow."
            exit 0
          fi
          HASH=$(printf '%s' "fl-edit-v1|$EDIT_PASSWORD" | sha256sum | cut -d' ' -f1)
          sed -i -E "s/let EDIT_PWD_HASH='[^']*'/let EDIT_PWD_HASH='$HASH'/" index.html
          if ! grep -q "let EDIT_PWD_HASH='$HASH'" index.html; then
            echo "::error::Non ho trovato la riga EDIT_PWD_HASH in index.html: carica l'ultima versione dell'app."
            exit 1
          fi
          echo "Hash della password iniettato in index.html: $HASH"

      - name: Pubblica (solo se e cambiato qualcosa)
        run: |
          if git diff --quiet; then
            echo "Hash gia aggiornato: nessun commit."
          else
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add index.html
            git commit -m "Applica password di modifica (hash)"
            git push
          fi
```

## Contenuto di `.github/workflows/update-cards.yml` (da copiare al passo 3)

```yaml
name: Aggiorna catalogo carte

on:
  schedule:
    # Ogni lunedì alle 04:00 UTC (06:00 ora italiana) — aggiornamento automatico
    - cron: "0 4 * * 1"
  workflow_dispatch:
    inputs:
      min_overall:
        description: "Rating minimo del catalogo (default 45 = tutto il database FutGenie)"
        required: false
        default: "45"
      deepen:
        description: "Punti sotto il rating minimo attuale da raggiungere ad ogni run (default 20)"
        required: false
        default: "20"
      max_pages:
        description: "Pagine massime da scaricare (48 carte per pagina; il DB completo è ~460)"
        required: false
        default: "500"

permissions:
  contents: write

jobs:
  update-cards:
    runs-on: ubuntu-latest
    steps:
      - name: Scarica il repository
        uses: actions/checkout@v4

      - name: Prepara Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Conta le carte attuali (per il controllo di sicurezza)
        run: |
          python3 - <<'PY'
          import json, os
          n = 0
          if os.path.exists('cards.json'):
              try:
                  n = len(json.load(open('cards.json')).get('cards', []))
              except Exception:
                  n = 0
          open('/tmp/count_before.txt', 'w').write(str(n))
          print('Carte nel catalogo attuale:', n)
          PY

      - name: Aggiorna il catalogo (merge incrementale — mantiene le esistenti, aggiunge le nuove)
        run: |
          python3 fut_scraper.py --dump-all --merge \
            --min-overall "${{ github.event.inputs.min_overall || '45' }}" \
            --deepen "${{ github.event.inputs.deepen || '20' }}" \
            --max-pages "${{ github.event.inputs.max_pages || '500' }}" \
            --delay 0.35 --year 27 --out cards.json

      - name: Controllo di sicurezza (il catalogo non può accorciarsi)
        run: |
          python3 - <<'PY'
          import json
          before = int(open('/tmp/count_before.txt').read().strip() or '0')
          n = len(json.load(open('cards.json')).get('cards', []))
          if n < 200:
              raise SystemExit('Catalogo troppo piccolo (%d carte): probabile problema con FutGenie. Mi fermo per non sovrascrivere il catalogo esistente.' % n)
          if before and n < before:
              raise SystemExit('Il catalogo si è accorciato (%d -> %d): merge fallito. Mi fermo.' % (before, n))
          print('Catalogo OK: %d carte (prima: %d)' % (n, before))
          PY

      - name: Riepilogo nel log del job
        run: |
          python3 - <<'PY'
          import json, os
          d = json.load(open('cards.json'))
          cards = d.get('cards', [])
          before = int(open('/tmp/count_before.txt').read().strip() or '0')
          ratings = [c.get('rating') or 0 for c in cards]
          lines = [
              '## Catalogo aggiornato',
              '',
              '- Carte totali: **%d**' % len(cards),
              '- Range rating: %d–%d' % (min(ratings), max(ratings)),
              '- Nuove carte aggiunte in questo run: **%d**' % (len(cards) - before),
              '',
              'Il sito (GitHub Pages) usa questo file automaticamente.',
          ]
          if os.environ.get('GITHUB_STEP_SUMMARY'):
              with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
                  f.write('\n'.join(lines) + '\n')
          print('\n'.join(lines))
          PY

      - name: Pubblica il catalogo aggiornato (il sito si aggiorna da solo)
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add cards.json
          if git diff --cached --quiet; then
            echo "Catalogo invariato: nessun commit."
          else
            git commit -m "Aggiorna catalogo carte ($(date -u +%Y-%m-%d))"
            git push
          fi
```
