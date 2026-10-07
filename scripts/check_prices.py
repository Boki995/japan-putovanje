#!/usr/bin/env python3
"""Dnevna provera cena letova BEG/BUD <-> Tokio/Osaka iz više izvora.

Izvori (svaki se uključuje ako postoji njegov ključ):
  1. Google Flights preko SerpApi (SERPAPI_KEY) - tačni termini, 6 putnika.
     Svako pokretanje proveri SEARCHES_PER_RUN kombinacija datuma redom kroz prozor.
  2. Aviasales preko Travelpayouts Data API (TRAVELPAYOUTS_TOKEN) - najjeftinije
     karte koje su drugi korisnici našli u poslednjih nekoliko dana, ceo prozor odjednom.

Za svaku nađenu kartu sajt pravi i linkove za Skyscanner, Kayak i Momondo
sa istim datumima i brojem putnika, radi brzog poređenja.

Rezultati: data/latest.json, data/history.json. Upozorenje (ntfy i/ili GitHub issue)
kad je cena ispod cilja.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

# ---------------- PODEŠAVANJA ----------------
ORIGINS = ["BEG", "BUD"]
DESTS = ["HND", "NRT", "KIX"]
CITY = {"HND": "TYO", "NRT": "TYO", "TYO": "TYO", "KIX": "OSA", "ITM": "OSA", "OSA": "OSA"}
FIRST_DEPARTURE = date(2027, 4, 10)
LAST_DEPARTURE = date(2027, 5, 15)
MIN_STAY = 15
MAX_STAY = 30                     # Aviasales: preskoči duže boravke (stavi 999 za bez ograničenja)
STAY_DAYS = [15, 18, 21]          # trajanje boravka za Google Flights pretrage
ADULTS = int(os.getenv("ADULTS", "6"))
TARGET_PER_PERSON = float(os.getenv("TARGET_EUR", "750"))
SEARCHES_PER_RUN = int(os.getenv("SEARCHES_PER_RUN", "8"))   # 8 x 31 = 248 < 250 besplatnih
# Google Flights prikazuje UKUPNU cenu za sve putnike. Ako se pokaže drugačije, postavi na "false".
PRICE_IS_TOTAL = os.getenv("PRICE_IS_TOTAL", "true").lower() == "true"
ROUTES = ["BEG-TYO", "BEG-OSA", "BUD-TYO", "BUD-OSA"]
KEEP_DAYS = 21                    # koliko dugo važi stara cena za "najbolje"
# ---------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LATEST = os.path.join(DATA, "latest.json")
HISTORY = os.path.join(DATA, "history.json")
STATE = os.path.join(DATA, "state.json")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def get_json(url, headers=None, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "japan-letovi/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def in_window(dep, ret):
    try:
        d, r = date.fromisoformat(dep[:10]), date.fromisoformat(ret[:10])
    except (TypeError, ValueError):
        return False
    return FIRST_DEPARTURE <= d <= LAST_DEPARTURE and MIN_STAY <= (r - d).days <= MAX_STAY


# ---------------- linkovi za poređenje ----------------
def compare_links(o, dest_airport, dep, ret):
    """Linkovi na iste datume i broj putnika na drugim sajtovima."""
    city = CITY.get(dest_airport, dest_airport)
    sky_dest = {"TYO": "tyoa", "OSA": "osaa"}.get(city, city.lower())
    yymmdd = lambda s: s[2:4] + s[5:7] + s[8:10]
    ddmm = lambda s: s[8:10] + s[5:7]
    return {
        "skyscanner": f"https://www.skyscanner.net/transport/flights/{o.lower()}/{sky_dest}/{yymmdd(dep)}/{yymmdd(ret)}/?adultsv2={ADULTS}&cabinclass=economy&currency=EUR",
        "kayak": f"https://www.kayak.com/flights/{o}-{city}/{dep}/{ret}/{ADULTS}adults?sort=price_a",
        "momondo": f"https://www.momondo.com/flight-search/{o}-{city}/{dep}/{ret}/{ADULTS}adults?sort=price_a",
        "aviasales": f"https://www.aviasales.com/search/{o}{ddmm(dep)}{city}{ddmm(ret)}{ADULTS}",
        "google": gflights_link(o, city, dep, ret),
    }


def gflights_link(o, city, dep, ret):
    dest = {"TYO": "HND,NRT", "OSA": "KIX"}.get(city, city)
    q = f"Flights from {o} to {dest} on {dep} through {ret} for {ADULTS} adults"
    return "https://www.google.com/travel/flights?" + urllib.parse.urlencode({"q": q, "curr": "EUR", "hl": "en"})


# ---------------- izvor 1: Google Flights (SerpApi) ----------------
def all_combos():
    out, d = [], FIRST_DEPARTURE
    while d <= LAST_DEPARTURE:
        for s in STAY_DAYS:
            out.append((d.isoformat(), (d + timedelta(days=s)).isoformat()))
        d += timedelta(days=1)
    return out


def serpapi(dep, ret, key):
    params = {"engine": "google_flights", "departure_id": ",".join(ORIGINS), "arrival_id": ",".join(DESTS),
              "outbound_date": dep, "return_date": ret, "type": "1", "adults": str(ADULTS),
              "currency": "EUR", "hl": "en", "gl": "rs", "api_key": key}
    return get_json("https://serpapi.com/search.json?" + urllib.parse.urlencode(params))


def parse_serpapi(resp, dep, ret):
    gurl = (resp.get("search_metadata") or {}).get("google_flights_url")
    best = {}
    for opt in (resp.get("best_flights") or []) + (resp.get("other_flights") or []):
        legs, price = opt.get("flights") or [], opt.get("price")
        if not legs or not isinstance(price, (int, float)):
            continue
        o = (legs[0].get("departure_airport") or {}).get("id")
        a = (legs[-1].get("arrival_airport") or {}).get("id")
        if o not in ORIGINS or a not in CITY:
            continue
        rid = f"{o}-{CITY[a]}"
        pp = price / ADULTS if PRICE_IS_TOTAL else price
        if rid in best and best[rid]["per_person"] <= pp:
            continue
        airlines = []
        for l in legs:
            if l.get("airline") and l["airline"] not in airlines:
                airlines.append(l["airline"])
        links = compare_links(o, a, dep, ret)
        best[rid] = {"source": "Google Flights", "per_person": round(pp), "total": round(pp * ADULTS),
                     "airlines": ", ".join(airlines), "stops": len(legs) - 1,
                     "duration_min": opt.get("total_duration"),
                     "via": ", ".join(l["arrival_airport"]["id"] for l in legs[:-1] if l.get("arrival_airport")),
                     "from_airport": o, "to_airport": a, "dep": dep, "ret": ret,
                     "url": gurl or links["google"], "compare": links}
    return best


def run_serpapi(key, state, latest, today):
    combos = all_combos()
    cur = state.get("cursor", 0) % len(combos)
    batch = [combos[(cur + i) % len(combos)] for i in range(min(SEARCHES_PER_RUN, len(combos)))]
    state["cursor"] = (cur + len(batch)) % len(combos)
    found = []
    for dep, ret in batch:
        k = f"{dep}_{ret}"
        try:
            resp = serpapi(dep, ret, key)
            if resp.get("error"):
                print("SerpApi", k, "greška:", resp["error"]); continue
            routes = parse_serpapi(resp, dep, ret)
        except Exception as e:
            print("SerpApi", k, "greška:", e); continue
        latest["combos"][k] = {"dep": dep, "ret": ret, "checked": today, "routes": routes}
        print("Google Flights", k, {r: v["per_person"] for r, v in routes.items()})
        found += [{"route": r, **v} for r, v in routes.items()]
    return found


# ---------------- izvor 2: Aviasales (Travelpayouts) ----------------
AIRLINES = {"SU": "Aeroflot", "TK": "Turkish Airlines", "VF": "AJet", "JU": "Air Serbia", "QR": "Qatar Airways",
            "EK": "Emirates", "EY": "Etihad", "LH": "Lufthansa", "OS": "Austrian", "LX": "Swiss", "AF": "Air France",
            "KL": "KLM", "AY": "Finnair", "LO": "LOT", "MU": "China Eastern", "CZ": "China Southern", "CA": "Air China",
            "KE": "Korean Air", "OZ": "Asiana", "NH": "ANA", "JL": "Japan Airlines", "W6": "Wizz Air", "W4": "Wizz Air Malta",
            "FR": "Ryanair", "PC": "Pegasus", "HU": "Hainan", "CX": "Cathay Pacific", "SQ": "Singapore Airlines",
            "BA": "British Airways", "IB": "Iberia", "AZ": "ITA Airways", "SK": "SAS", "HY": "Uzbekistan Airways",
            "KC": "Air Astana", "MS": "EgyptAir", "WY": "Oman Air", "GF": "Gulf Air", "SV": "Saudia", "FZ": "flydubai"}


def month_pairs():
    months = []
    m = date(FIRST_DEPARTURE.year, FIRST_DEPARTURE.month, 1)
    while m <= LAST_DEPARTURE:
        months.append(m)
        m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)
    pairs = []
    for dm in months:
        nxt = date(dm.year + (dm.month // 12), dm.month % 12 + 1, 1)
        for rm in (dm, nxt):
            pairs.append((dm.strftime("%Y-%m"), rm.strftime("%Y-%m")))
    return pairs


def run_aviasales(token, latest, today):
    found, seen = [], set()
    for o in ORIGINS:
        for city in ("TYO", "OSA"):
            for dm, rm in month_pairs():
                params = {"origin": o, "destination": city, "departure_at": dm, "return_at": rm,
                          "one_way": "false", "currency": "eur", "sorting": "price", "limit": "1000",
                          "token": token}
                try:
                    resp = get_json("https://api.travelpayouts.com/aviasales/v3/prices_for_dates?"
                                    + urllib.parse.urlencode(params), headers={"X-Access-Token": token})
                except Exception as e:
                    print("Aviasales", o, city, dm, rm, "greška:", e); continue
                for t in resp.get("data") or []:
                    dep, ret = (t.get("departure_at") or "")[:10], (t.get("return_at") or "")[:10]
                    price = t.get("price")
                    if not isinstance(price, (int, float)) or not in_window(dep, ret):
                        continue
                    a = t.get("destination_airport") or city
                    key = (o, city, dep, ret, price, t.get("airline"))
                    if key in seen:
                        continue
                    seen.add(key)
                    links = compare_links(o, a, dep, ret)
                    link = t.get("link")
                    stops = (t.get("transfers") or 0)
                    code = t.get("airline") or ""
                    found.append({"route": f"{o}-{city}", "source": "Aviasales", "per_person": round(price),
                                  "total": round(price * ADULTS), "airlines": AIRLINES.get(code, code),
                                  "stops": stops, "duration_min": t.get("duration_to"), "via": "",
                                  "from_airport": t.get("origin_airport") or o, "to_airport": a,
                                  "dep": dep, "ret": ret,
                                  "url": ("https://www.aviasales.com" + link) if link and link.startswith("/") else links["aviasales"],
                                  "compare": links, "note": "keš cena za 1 putnika"})
    found.sort(key=lambda x: x["per_person"])
    latest["aviasales"] = {"checked": today, "deals": found[:80]}
    print("Aviasales: nađeno", len(found), "karata u prozoru")
    return found


# ---------------- upozorenja ----------------
def notify(alerts, today):
    if not alerts:
        return
    lines = [f"{a['route']} ({a['source']}): €{a['per_person']}/os (€{a['total']} za {ADULTS}) · {a['dep']} → {a['ret']} · {a['airlines']}\n{a['url']}\nSkyscanner: {a['compare']['skyscanner']}"
             for a in alerts]
    body = "Cene ispod cilja (€%d po osobi):\n\n%s" % (TARGET_PER_PERSON, "\n\n".join(lines))
    title = f"Japan letovi: €{alerts[0]['per_person']}/os ({alerts[0]['route']})"
    topic = os.getenv("NTFY_TOPIC")
    if topic:
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                         headers={"Title": title, "Tags": "airplane", "Priority": "high",
                                                  "Click": alerts[0]["url"]})
            urllib.request.urlopen(req, timeout=30); print("ntfy poslat")
        except Exception as e:
            print("ntfy greška:", e)
    gh_token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if gh_token and repo and os.getenv("ISSUE_ALERTS", "true").lower() == "true":
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/issues",
                data=json.dumps({"title": f"{title} · {today}", "body": body}).encode(),
                headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
                method="POST")
            urllib.request.urlopen(req, timeout=30); print("GitHub issue otvoren (stiže mejl)")
        except Exception as e:
            print("GitHub issue greška:", e)


def main():
    serp_key, tp_token = os.getenv("SERPAPI_KEY"), os.getenv("TRAVELPAYOUTS_TOKEN")
    if not serp_key and not tp_token:
        sys.exit("Nema nijednog ključa. Dodaj SERPAPI_KEY i/ili TRAVELPAYOUTS_TOKEN u Settings → Secrets → Actions.")
    os.makedirs(DATA, exist_ok=True)
    today = datetime.now(timezone(timedelta(hours=1))).date().isoformat()
    state = load(STATE, {"cursor": 0})
    latest = load(LATEST, {"combos": {}})
    latest.setdefault("combos", {})
    history = load(HISTORY, [])

    new = []
    if serp_key:
        new += run_serpapi(serp_key, state, latest, today)
    if tp_token:
        new += run_aviasales(tp_token, latest, today)

    # najbolja cena po ruti preko svih izvora (cene ne starije od KEEP_DAYS)
    cutoff = (date.fromisoformat(today) - timedelta(days=KEEP_DAYS)).isoformat()
    latest["combos"] = {k: c for k, c in latest["combos"].items() if c["checked"] >= cutoff}
    pool = []
    for c in latest["combos"].values():
        pool += [{"route": r, "checked": c["checked"], **v} for r, v in c["routes"].items()]
    av = latest.get("aviasales") or {}
    if av.get("checked", "") >= cutoff:
        pool += [{**d, "checked": av["checked"]} for d in av.get("deals", [])]
    best = {}
    for p in pool:
        if p["route"] not in best or p["per_person"] < best[p["route"]]["per_person"]:
            best[p["route"]] = p
    latest["best"] = best
    latest["updated"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    latest["config"] = {"adults": ADULTS, "target": TARGET_PER_PERSON,
                        "window": [FIRST_DEPARTURE.isoformat(), LAST_DEPARTURE.isoformat()],
                        "stays": STAY_DAYS, "min_stay": MIN_STAY, "combos_total": len(all_combos()),
                        "combos_checked": len(latest["combos"]),
                        "sources": [s for s, on in (("Google Flights", serp_key), ("Aviasales", tp_token)) if on]}

    history = [h for h in history if h.get("date") != today]
    history.append({"date": today, "best": {r: best[r]["per_person"] for r in best}})
    history.sort(key=lambda h: h["date"])

    save(LATEST, latest); save(HISTORY, history); save(STATE, state)

    # javi samo za karte koje još nisu javljene (ista ruta, datumi i cena)
    sent = set(state.get("alerted", []))
    alerts = []
    for n in sorted(new, key=lambda a: a["per_person"]):
        k = f"{n['route']}|{n['dep']}|{n['ret']}|{n['per_person']}"
        if n["per_person"] <= TARGET_PER_PERSON and k not in sent and len(alerts) < 5:
            alerts.append(n); sent.add(k)
    state["alerted"] = sorted(sent)[-500:]
    save(STATE, state)
    notify(alerts[:5], today)


if __name__ == "__main__":
    main()
