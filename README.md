# FIFTEEN LEAGUE — Pubblicazione su GitHub Pages

Questo pacchetto rende l'app **completamente autonoma**: la ricerca delle carte
(nome + foto) funziona appena la pagina è online, **senza script da avviare,
senza Python sul tuo computer, senza proxy**.

## Cosa contiene

| File | A cosa serve |
|------|--------------|
| `index.html` | L'app completa (tutto in un file) |
| `cards.json` | Catalogo iniziale: 1106 giocatori (rating 80–95) con foto carta |
| `fut_scraper.py` | Lo scraper che **GitHub** eseguirà per aggiornare il catalogo |
| `requirements.txt` | Dipendenze opzionali dello scraper (per la strategia futbin, non serve a FutGenie) |
| `.github/workflows/update-cards.yml` | L'automazione che aggiorna `cards.json` e rideploya il sito |

## Come funziona (in 10 secondi)

- L'app, appena aperta, scarica `cards.json` **dal suo stesso sito** (stesso
  dominio → nessun problema CORS, nessun proxy).
- Le immagini delle carte arrivano dal CDN di FutGenie (`assets.futgenie.gg`).
- Un'automazione di GitHub ("Actions") rilancia lo scraper ogni lunedì e
  aggiorna `cards.json`: il sito si aggiorna da solo. Puoi lanciarla anche
  a mano quando vuoi.

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

Fatto. Apri il link: la ricerca carte funziona subito con 1106 giocatori.

### 5 — Aggiornare il catalogo (quando vuoi / ogni lunedì automatico)
- Manuale: nel repository → scheda **Actions** →
  **Aggiorna catalogo carte** → **Run workflow** → **Run workflow** (verde).
  In ~3–5 minuti `cards.json` viene rigenerato (rating 78+, oltre 3000 carte)
  e il sito si aggiorna da solo.
- Automatico: il workflow gira ogni lunedì alle 06:00 ora italiana.
- Se FutGenie avesse problemi, un controllo di sicurezza impedisce di
  sovrascrivere il catalogo con uno vuoto.

---

## Note

- **I dati della lega (rose, giornate, classifica)** restano nel **browser**
  (localStorage del dominio). Nessun server li conserva: usa **Esporta DB**
  (menu in alto) per fare backup o spostare i dati su un altro dispositivo,
  e **Importa** per ripristinarli.
- **`fut_proxy.py` non serve più**: era solo per aggirare il CORS da file
  locale. Con il sito online il catalogo arriva dalla pagina stessa.
- La ricerca "Live FutGenie" resta come extra facoltativo (utile solo se
  servisse una carta fuori catalogo), ma non è necessaria.
- Le immagini sono caricate dal CDN di FutGenie: serve una connessione internet.
- Usa il catalogo per uso personale e con richieste limitate (il workflow fa
  ~120 richieste a settimana, un ritmo rispettoso).

---

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
        description: "Rating minimo del catalogo (default 78)"
        required: false
        default: "78"

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

      - name: Scarica il catalogo da FutGenie (API pubbliche, senza segreti)
        run: |
          python3 fut_scraper.py --dump-all \
            --min-overall "${{ github.event.inputs.min_overall || '78' }}" \
            --max-pages 120 --delay 0.6 --year 27 --out cards.json

      - name: Controllo di sicurezza sul catalogo
        run: |
          python3 - <<'PY'
          import json
          d = json.load(open('cards.json'))
          n = len(d.get('cards', []))
          if n < 200:
              raise SystemExit('Catalogo troppo piccolo (%d carte): probabile problema con FutGenie. Mi fermo per non sovrascrivere il catalogo esistente.' % n)
          print('Catalogo OK: %d carte' % n)
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
