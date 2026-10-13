#!/usr/bin/env python3
"""
FIFTEEN LEAGUE — Scraper carte FUT (FutGenie / Futbin / fut.gg)
===============================================================
Genera un file cards.json nel formato importabile dalla webapp FIFTEEN LEAGUE
(tab "Rose" -> "Importa DB carte (JSON)").

STRATEGIE (in modalità --players vengono provate in ordine, la prima che
funziona vince):
  S5  FUTGENIE ⭐  - API PUBBLICHE di futgenie.gg: NESSUN Cloudflare, funziona
                      ovunque (casa, datacenter, GitHub Actions). Restituisce
                      nome, rating, posizione + immagine CARTA PNG su CDN e
                      club/nazione/tipo dalla pagina dettaglio. STRATEGIA
                      PRINCIPALE.
  S1  HTML OFFLINE  - parser di pagine HTML salvate dal TUO browser (infallibile
                      per futbin/fut.gg: tu apri il sito, salvi la pagina in
                      pages/ e lo script la converte in JSON)
  S2  CURL_CFFI     - richieste HTTP con fingerprint TLS Chrome reale verso
                      futbin/fut.gg (spesso bloccate da Cloudflare)
  S3  FLARESOLVERR  - se FLARESOLVERR_URL e' impostata (es. http://localhost:8191)
                      usa il solver locale; compatibile con un tunnel casalingo
  S4  API INTERNE   - sonda endpoint JSON interni di fut.gg (se attivi)

USO RAPIDO:
  python3 fut_scraper.py --players "Messi, Ronaldo, Buffon"
  python3 fut_scraper.py --players-file players.txt
  python3 fut_scraper.py --players "Messi" --merge          # unisce al DB esistente
  python3 fut_scraper.py --players "Messi" --no-details     # piu' veloce, niente club/nazione
  python3 fut_scraper.py --dump-all --min-overall 80        # DB completo fino a 80
  python3 fut_scraper.py --offline pages/                   # S1: HTML salvati dal browser

OUTPUT: cards.json  ->  {format, version, cards:[{name, rating, pos, club, nation, type, img}]}
NOTE:
 - Il campo img punta al CDN di futgenie (assets.futgenie.gg/cards/<id>.png):
   la webapp mostra la carta direttamente via hotlink, niente da scaricare.
 - I dati delle carte (rating, carta speciale) cambiano nel corso della stagione:
   riesegui lo scraper e reimporta il JSON nell'app (con --merge si somma).
 - FutGenie e' aperto: funziona anche dal workflow GitHub Actions senza segreti.
 - Rispetta i termini di servizio dei siti: uso personale, richieste limitate (--delay).
"""
import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

FUTBIN_SEARCH = "https://www.futbin.com/search?year={year}&term={term}"
FUTBIN_PLAYERS = "https://www.futbin.com/players?page=1&search={term}&version={ver}"
FUTGG_SEARCH = "https://fut.gg/players/?name={term}"
FUTGG_API = "https://fut.gg/api/players/?search={term}"

# S5: FutGenie (API pubbliche, senza Cloudflare)
FUTGENIE_BASE = "https://www.futgenie.gg"
FUTGENIE_SUGGEST = FUTGENIE_BASE + "/api/players/search-suggestions?q={term}&limit=8&year={year}"
FUTGENIE_PLAYERS = FUTGENIE_BASE + "/api/players?page={page}&year={year}"
FUTGENIE_FILTERS = FUTGENIE_BASE + "/api/players/filters?year={year}"
FUTGENIE_ITEM_PAGE = FUTGENIE_BASE + "/player-items/{id}"
FUTGENIE_CARD_IMG = "https://assets.futgenie.gg/cards/{id}.png"
FUTGENIE_BADGE_RE = re.compile(r'href="/players\?([a-zA-Z]+Ids?)=(\d+)">([^<]+)</a>')

SPECIAL_HINTS = [
    ("TOTW", ["totw", "team of the week", "in form"]),
    ("OTW", ["otw", "ones to watch"]),
    ("Icon", ["icon"]),
    ("Hero", ["hero"]),
    ("TOTS", ["tots", "team of the season"]),
    ("Special", ["sbc", "event", "promo", "special"]),
]


def log(msg: str) -> None:
    print(msg, flush=True)


def norm_text(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def guess_type(text: str, default=""):
    t = (text or "").lower()
    for label, hints in SPECIAL_HINTS:
        if any(h in t for h in hints):
            return label
    return default


def make_card(name, rating, pos, club, nation, ctype, img):
    """Normalizza una carta nel formato della webapp."""
    name = norm_text(name)
    if not name:
        return None
    try:
        rating = int(str(rating).strip()) if str(rating).strip().isdigit() else ""
    except Exception:
        rating = ""
    if rating and (rating < 1 or rating > 99):
        rating = ""
    card = {
        "name": name,
        "rating": rating,
        "pos": norm_text(pos).upper()[:3] if pos else "",
        "club": norm_text(club),
        "nation": norm_text(nation),
        "type": norm_text(ctype),
        "img": (img or "").strip(),
    }
    if card["img"].startswith("//"):
        card["img"] = "https:" + card["img"]
    if card["img"].startswith("http://"):
        card["img"] = "https://" + card["img"][7:]
    return card


# ----------------------------------------------------------------------------
# PARSER HTML (usato sia da S1 che da S2): tollerante su futbin e fut.gg
# ----------------------------------------------------------------------------

def extract_cards_from_html(html: str, source: str = ""):
    """Estrae carte da HTML di futbin/fut.gg con multiple euristiche."""
    from bs4 import BeautifulSoup
    cards = []
    soup = BeautifulSoup(html, "html.parser")

    # --- euristica 1: righe tabella futbin (classe storica .table-player) ---
    for row in soup.select(".table-player, tr[data-playerid], .player-row"):
        name_el = row.select_one(".table-player-name a, .player-name, a[href*='/player/']")
        if not name_el:
            continue
        name = norm_text(name_el.get_text(" ", strip=True))
        rating_el = row.select_one(".card-title, .rating, .player-rating, [class*='rating']")
        rating = rating_el.get_text(" ", strip=True) if rating_el else ""
        pos_el = row.select_one(".alternative-position, .pos, [class*='position']")
        pos = pos_el.get_text(" ", strip=True) if pos_el else ""
        img = ""
        for sel in ("img[data-src*='players'], img[src*='players']",
                    "img[data-src*='faces'], img[src*='faces']",
                    "img[data-src*='cdn'], img[src*='cdn']"):
            for img_el in row.select(sel):
                img = img_el.get("src") or img_el.get("data-src") or ""
                if img:
                    break
            if img:
                break
        cards.append(make_card(name, rating, pos, "", "", guess_type(source), img))

    # --- euristica 2: link diretti a pagine giocatore (fut.gg card grid) ---
    if not cards:
        for a in soup.select("a[href*='/players/']"):
            name = norm_text(a.get_text(" ", strip=True))
            if not name or len(name) > 40:
                continue
            rating = ""
            r = a.select_one("[class*='rating']")
            if r:
                rating = r.get_text(" ", strip=True)
            img_el = a.select_one("img[src]")
            img = img_el.get("src", "") if img_el else ""
            cards.append(make_card(name, rating, "", "", "", guess_type(source), img))

    # --- euristica 3: JSON autocomplete inline dentro la pagina ---
    if not cards:
        for m in re.finditer(r"\[(?:\s*\{[^<>]{10,300}\},?){1,50}\]", html):
            try:
                data = json.loads(m.group(0))
                for item in data:
                    if isinstance(item, dict) and ("name" in item or "full_name" in item):
                        cards.append(make_card(
                            item.get("name") or item.get("full_name"),
                            item.get("rating"), item.get("position") or item.get("pos"),
                            item.get("club") or item.get("team"),
                            item.get("nation") or item.get("country"),
                            item.get("card") or item.get("type") or "",
                            item.get("img") or item.get("image") or ""))
            except Exception:
                continue

    return dedupe(cards)


# ----------------------------------------------------------------------------
# S1: HTML salvati dal browser (infallibile)
# ----------------------------------------------------------------------------

def run_offline(folder: str):
    pages = sorted(Path(folder).glob("*.html")) + sorted(Path(folder).glob("*.htm"))
    if not pages:
        log(f"[S1] Nessun file HTML in '{folder}'. Apri futbin/fut.gg nel browser, "
            f"cerca i giocatori, salva la pagina (Ctrl+S) come .html dentro '{folder}/'.")
        return []
    cards = []
    for p in pages:
        html = p.read_text(encoding="utf-8", errors="ignore")
        got = extract_cards_from_html(html, source=p.name)
        log(f"[S1] {p.name}: {len(got)} carte estratte")
        cards.extend(got)
    return dedupe(cards)


# ----------------------------------------------------------------------------
# S2: curl_cffi con fingerprint Chrome
# ----------------------------------------------------------------------------

def http_get(url: str, timeout=25):
    from curl_cffi import requests as cr
    return cr.get(url, impersonate="chrome", timeout=timeout,
                  headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.8"})


def run_curlcffi(term: str, year: int, save_html: bool, delay: float):
    out = []
    targets = [
        ("futbin-search", FUTBIN_SEARCH.format(year=year, term=term)),
        ("futbin-players", FUTBIN_PLAYERS.format(term=term, ver=year)),
        ("futgg", FUTGG_SEARCH.format(term=term)),
    ]
    for label, url in targets:
        try:
            r = http_get(url)
            if r.status_code != 200 or "Just a moment" in r.text[:2000]:
                log(f"[S2] {label}: bloccato (HTTP {r.status_code})")
                continue
            if save_html:
                Path("debug").mkdir(exist_ok=True)
                safe = re.sub(r"[^a-z0-9]+", "_", term.lower())[:20]
                Path(f"debug/{label}_{safe}.html").write_text(r.text, encoding="utf-8")
            got = extract_cards_from_html(r.text, source=label)
            log(f"[S2] {label}: {len(got)} carte")
            if got:
                out.extend(got)
                break
        except Exception as e:
            log(f"[S2] {label}: errore ({e.__class__.__name__}: {e})")
        time.sleep(delay + random.uniform(0, delay / 2))
    return dedupe(out)


# ----------------------------------------------------------------------------
# S3: FlareSolverr
# ----------------------------------------------------------------------------

def run_flaresolverr(term: str, year: int):
    import requests
    base = os.environ.get("FLARESOLVERR_URL", "").rstrip("/")
    if not base:
        return []
    url = FUTBIN_PLAYERS.format(term=term, ver=year)
    try:
        r = requests.post(base + "/v1", json={"cmd": "request.get", "url": url,
                                              "maxTimeout": 60000}, timeout=70)
        sol = r.json()
        if sol.get("status") != "ok":
            log(f"[S3] FlareSolverr: status {sol.get('status')}")
            return []
        html = sol.get("solution", {}).get("response", "")
        got = extract_cards_from_html(html, source="flaresolverr")
        log(f"[S3] FlareSolverr: {len(got)} carte")
        return got
    except Exception as e:
        log(f"[S3] FlareSolverr errore: {e}")
        return []


# ----------------------------------------------------------------------------
# S4: endpoint API interni
# ----------------------------------------------------------------------------

def run_api(term: str, year: int):
    out = []
    try:
        r = http_get(FUTGG_API.format(term=term), timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("results") or data.get("data") or []
            for it in items:
                if not isinstance(it, dict):
                    continue
                club = it.get("club")
                if isinstance(club, dict):
                    club = club.get("name") or ""
                nation = it.get("nation")
                if isinstance(nation, dict):
                    nation = nation.get("name") or ""
                out.append(make_card(
                    it.get("name") or it.get("commonName") or it.get("fullName"),
                    it.get("rating"), it.get("position") or it.get("pos"),
                    club, nation,
                    it.get("cardType") or it.get("type") or "",
                    it.get("image") or it.get("img") or ""))
        if out:
            log(f"[S4] fut.gg API: {len(out)} carte")
    except Exception:
        log("[S4] API interne non disponibili (atteso se protette)")
    return dedupe(out)


# ----------------------------------------------------------------------------
# S5: FutGenie — API pubbliche senza Cloudflare (strategia principale)
# ----------------------------------------------------------------------------

def plain_get(url: str, timeout=20, head=False):
    """GET/HEAD con urllib (stdlib, zero dipendenze). Ritorna (status, body)."""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "image/png,*/*" if head else "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    }, method="HEAD" if head else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = b"" if head else r.read()
            return r.status, (data.decode("utf-8", errors="ignore") if data else "")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _pick_best_suggestion(sugg, term: str):
    """Sceglie il miglior match: esatto > inizio nome > contenuto, poi rating alto."""
    tl = term.strip().lower()

    def rank(s):
        cn = (s.get("cardName") or s.get("name") or "").lower()
        fn = (s.get("name") or "").lower()
        ov = int(s.get("overall") or 0)
        if cn == tl or fn == tl:
            return (0, -ov)
        if cn.startswith(tl) or fn.startswith(tl):
            return (1, -ov)
        if tl in cn or tl in fn:
            return (2, -ov)
        return (3, -ov)

    return sorted(sugg, key=rank)[0]


def run_futgenie(term: str, year, delay: float, with_details=True):
    """Cerca un giocatore su FutGenie: nome/rating/posizione dall'API di ricerca,
    immagine carta dal CDN, club/nazione/tipo dalla pagina dettaglio."""
    from urllib.parse import quote_plus
    st, body = plain_get(FUTGENIE_SUGGEST.format(term=quote_plus(term), year=year))
    if st != 200:
        log(f"[S5] futgenie: ricerca non disponibile (HTTP {st})")
        return []
    try:
        sugg = json.loads(body)
    except Exception:
        log("[S5] futgenie: risposta ricerca non valida")
        return []
    if not sugg:
        log(f"[S5] futgenie: nessun risultato per '{term}'")
        return []

    best = _pick_best_suggestion(sugg, term)
    pid = best.get("id")
    cname = best.get("cardName") or best.get("name") or term
    overall = best.get("overall", "")
    pos = best.get("position", "")

    img = FUTGENIE_CARD_IMG.format(id=pid)
    st_img, _ = plain_get(img, head=True)
    if st_img != 200:
        img = FUTGENIE_BASE + "/api/card-images/" + str(pid)

    club = nation = ctype = ""
    if with_details:
        time.sleep(min(delay, 1.5) + random.uniform(0, 0.4))
        st_d, html = plain_get(FUTGENIE_ITEM_PAGE.format(id=pid), timeout=25)
        if st_d == 200 and html:
            found = {}
            for kind, _bid, label in FUTGENIE_BADGE_RE.findall(html):
                found.setdefault(kind, norm_text(label))
            ctype = found.get("rarityIds", "")
            club = found.get("clubIds", "")
            nation = found.get("nationIds", "")

    extra = " · ".join(x for x in (club, nation, ctype) if x)
    log(f"[S5] futgenie: '{term}' -> {cname} {overall} {pos}"
        + (f" ({extra})" if extra else "")
        + (" [img OK]" if st_img == 200 else " [img da verificare]"))
    card = make_card(cname, overall, pos, club, nation, ctype, img)
    return [card] if card else []


def run_futgenie_dump(year, min_overall: int, max_pages: int, delay: float):
    """Scarica in blocco il database FutGenie (ordinato per rating decrescente)
    fermandosi sotto la soglia --min-overall. Usa /api/players/filters per
    convertire gli id di club/nazione in nomi."""
    maps = {"clubIds": {}, "nationIds": {}}
    st, body = plain_get(FUTGENIE_FILTERS.format(year=year), timeout=40)
    if st == 200:
        try:
            f = json.loads(body)
            maps["clubIds"] = {c.get("id"): c.get("name", "") for c in f.get("clubs", []) or []}
            maps["nationIds"] = {n.get("id"): n.get("name", "") for n in f.get("nations", []) or []}
            log(f"[S5] filtri caricati: {len(maps['clubIds'])} club, {len(maps['nationIds'])} nazioni")
        except Exception:
            log("[S5] filtri non leggibili (continuo senza club/nazione)")

    cards, page, stopped = [], 1, False
    while page <= max_pages:
        st, body = plain_get(FUTGENIE_PLAYERS.format(page=page, year=year))
        if st != 200:
            log(f"[S5] dump: pagina {page} HTTP {st}, mi fermo")
            break
        try:
            d = json.loads(body)
        except Exception:
            break
        ps = d.get("players", [])
        if not ps:
            break
        for p in ps:
            ov = int(p.get("overall") or 0)
            if min_overall and ov < min_overall:
                stopped = True
                break
            pl = p.get("player") or {}
            cards.append(make_card(
                pl.get("cardName") or pl.get("name"),
                ov, p.get("position", ""),
                maps["clubIds"].get(p.get("teamId"), ""),
                maps["nationIds"].get(p.get("nationId"), ""),
                "",
                FUTGENIE_CARD_IMG.format(id=p.get("id"))))
        if stopped:
            break
        log(f"[S5] dump: pagina {page} ok ({len(cards)} carte finora)")
        if not d.get("hasMore"):
            break
        page += 1
        time.sleep(delay)
    log(f"[S5] dump completato: {len(cards)} carte (soglia overall {min_overall})")
    return dedupe(cards)


# ----------------------------------------------------------------------------
# util
# ----------------------------------------------------------------------------

def _rate(c):
    """Rating numerico di una carta (0 se mancante/non valido)."""
    try:
        return int(str(c.get("rating") or 0).strip() or 0)
    except (TypeError, ValueError):
        return 0


def cat_key(c):
    """Chiave unica di una carta: nome + immagine. Due carte con stessa immagine
    sono la stessa carta; versioni diverse (base/TOTW/promo) restano distinte."""
    return (str(c.get("name", "")).lower(), str(c.get("img", "")))


def dedupe(cards):
    """Unisce i duplicati della STESSA carta (nome + immagine). Versioni diverse
    dello stesso giocatore (base, TOTW, promo...) hanno immagini diverse e vengono
    tutte mantenute, cosi' la ricerca in app le mostra tutte."""
    seen, out = set(), []
    for c in cards:
        if not c:
            continue
        key = c["name"].lower() + "|" + c["img"]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def merge_catalog(old_cards, new_cards):
    """Merge incrementale: mantiene TUTTE le carte esistenti e aggiunge solo le
    nuove (stessa carta = stesso nome + stessa immagine). Il catalogo cresce
    run dopo run e non perde mai carte. Ritorna (lista_unita, n_nuove)."""
    old_cards = [c for c in old_cards if c]
    old_keys = {cat_key(c) for c in old_cards}
    fresh = [c for c in new_cards if c and cat_key(c) not in old_keys]
    merged = sorted(dedupe(old_cards + fresh), key=lambda c: -_rate(c))
    return merged, len(fresh)


def load_existing(out_path: str):
    p = Path(out_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            return data["cards"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def main():
    ap = argparse.ArgumentParser(description="Scraper carte FUT -> cards.json per FIFTEEN LEAGUE")
    ap.add_argument("--players", help="nomi separati da virgola: \"Messi, Ronaldo\"")
    ap.add_argument("--players-file", help="file .txt con un nome per riga")
    ap.add_argument("--offline", metavar="DIR", help="parsifica file .html salvati dal browser (S1)")
    ap.add_argument("--dump-all", action="store_true",
                    help="scarica in blocco il DB FutGenie fino a --min-overall (senza ricerca per nome)")
    ap.add_argument("--min-overall", type=int, default=80,
                    help="rating minimo (pavimento) per --dump-all: mai scaricato sotto "
                         "questo valore (default 80; 45 = tutto il database FutGenie)")
    ap.add_argument("--max-pages", type=int, default=40,
                    help="pagine massime per --dump-all (default 40, ~48 carte per pagina; "
                         "il DB completo e' ~460 pagine)")
    ap.add_argument("--deepen", type=int, default=0,
                    help="con --dump-all --merge: scende di N punti sotto il rating minimo "
                         "del catalogo esistente (mai sotto --min-overall). "
                         "0 = usa solo --min-overall. Attiva --merge automaticamente")
    ap.add_argument("--no-details", action="store_true",
                    help="salta la pagina dettaglio FutGenie (piu' veloce, senza club/nazione)")
    ap.add_argument("--year", default="27", help="anno del gioco (default 27)")
    ap.add_argument("--out", default="cards.json", help="file di output (default cards.json)")
    ap.add_argument("--merge", action="store_true", help="unisci con il contenuto esistente di --out")
    ap.add_argument("--delay", type=float, default=1.0, help="pausa tra richieste in secondi (default 1)")
    ap.add_argument("--save-html", action="store_true", help="salva le risposte HTML in debug/ per analisi")
    args = ap.parse_args()

    names = []
    if args.players:
        names = [n.strip() for n in args.players.split(",") if n.strip()]
    elif args.players_file:
        names = [ln.strip() for ln in Path(args.players_file).read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]

    if args.offline:
        cards = run_offline(args.offline)
    elif args.dump_all:
        floor = args.min_overall
        effective = floor
        if args.deepen > 0:
            args.merge = True
            prev = load_existing(args.out)
            if prev:
                cur_min = min(_rate(c) for c in prev)
                if cur_min > 0:
                    effective = max(floor, cur_min - args.deepen)
                    log(f"[S5] approfondimento: catalogo attuale arriva a rating {cur_min} "
                        f"-> questa passata scarico fino a {effective}")
        cards = run_futgenie_dump(args.year, effective, args.max_pages, args.delay)
    else:
        if not names:
            ap.print_help()
            log("\nNessun giocatore indicato: usa --players, --players-file, --dump-all o --offline")
            sys.exit(1)
        cards = []
        for name in names:
            log(f"\n=== {name} ===")
            got = run_futgenie(name, args.year, args.delay, with_details=not args.no_details)
            if not got:
                got = run_curlcffi(name, args.year, args.save_html, args.delay)
            if not got:
                got = run_api(name, args.year)
            if not got:
                got = run_flaresolverr(name, args.year)
            if not got:
                log(f"[!!] '{name}' non trovato. Controlla l'ortografia (es. cardName della carta) "
                    f"oppure usa --offline pages/ con le pagine salvate dal browser.")
            cards.extend(got)
        cards = dedupe(cards)

    if args.merge:
        old_cards = load_existing(args.out)
        cards, n_new = merge_catalog(old_cards, cards)
        log(f"[merge] mantenute {len(old_cards)} carte esistenti · "
            f"aggiunte {n_new} nuove · totale {len(cards)}")

    payload = {"format": "fifteen-league-cards", "version": 1,
               "exportedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "cards": cards}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\nScritto {args.out}: {len(cards)} carte")
    if not cards:
        log("Nessuna carta estratta: prova la modalità --offline (vedi README).")


if __name__ == "__main__":
    main()
