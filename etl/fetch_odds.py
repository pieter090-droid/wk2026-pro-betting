"""
WK2026 Pro Betting - OddsPapi Odds ETL
1 call per dag voor alle WK odds: 1X2, BTTS, O/U 1.5/2.5/3.5/4.5
"""

import os
import requests
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ODDSPAPI_KEY = os.environ["ODDSPAPI_KEY"]
BASE_URL     = "https://api.oddspapi.io/v4"
SPORT_ID     = 10
BOOKMAKERS   = "pinnacle,bet365"
BATCH_SIZE   = 50

sb      = create_client(SUPABASE_URL, SUPABASE_KEY)
session = requests.Session()


def api_get(path, params):
    params["apiKey"]     = ODDSPAPI_KEY
    params["oddsFormat"] = "decimal"
    r = session.get(f"{BASE_URL}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_wk_id():
    print("[1/3] WK 2026 tournament ID ophalen...")
    data = api_get("tournaments", {"sportId": SPORT_ID})
    keywords = ["world cup", "fifa", "mundial"]
    for t in data:
        name = t.get("tournamentName", "").lower()
        if any(kw in name for kw in keywords):
            print(f"      Gevonden: {t['tournamentName']} (ID: {t['tournamentId']})")
            return t["tournamentId"]
    print("      Alle toernooien:")
    for t in data:
        print(f"        {t['tournamentId']}: {t['tournamentName']}")
    raise ValueError("WK 2026 niet gevonden")


def get_price(bm, market, outcome):
    try:
        p = bm.get("markets", {}).get(market, {})
        p = p.get("outcomes", {}).get(outcome, {})
        p = p.get("players", {})
        for v in p.values():
            if v.get("active"):
                return v.get("price")
    except Exception:
        pass
    return None


def process(fixture):
    fid  = fixture.get("fixtureId")
    bms  = fixture.get("bookmakerOdds", {})
    pin  = bms.get("pinnacle", {})
    b365 = bms.get("bet365", {})
    return {
        "fixture_id":    fid,
        "home_team":     fixture.get("participant1Name", ""),
        "away_team":     fixture.get("participant2Name", ""),
        "start_time":    fixture.get("startTime"),
        "tournament_id": fixture.get("tournamentId"),
        "status_id":     fixture.get("statusId", 0),
        "pin_home":      get_price(pin,  "101",  "101"),
        "pin_draw":      get_price(pin,  "101",  "102"),
        "pin_away":      get_price(pin,  "101",  "103"),
        "b365_home":     get_price(b365, "101",  "101"),
        "b365_draw":     get_price(b365, "101",  "102"),
        "b365_away":     get_price(b365, "101",  "103"),
        "pin_btts_yes":  get_price(pin,  "104",  "104"),
        "pin_btts_no":   get_price(pin,  "104",  "105"),
        "b365_btts_yes": get_price(b365, "104",  "104"),
        "b365_btts_no":  get_price(b365, "104",  "105"),
        "pin_over15":    get_price(pin,  "1012", "1012"),
        "pin_under15":   get_price(pin,  "1013", "1013"),
        "b365_over15":   get_price(b365, "1012", "1012"),
        "b365_under15":  get_price(b365, "1013", "1013"),
        "pin_over25":    get_price(pin,  "1010", "1010"),
        "pin_under25":   get_price(pin,  "1011", "1011"),
        "b365_over25":   get_price(b365, "1010", "1010"),
        "b365_under25":  get_price(b365, "1011", "1011"),
        "pin_over35":    get_price(pin,  "1014", "1014"),
        "pin_under35":   get_price(pin,  "1015", "1015"),
        "b365_over35":   get_price(b365, "1014", "1014"),
        "b365_under35":  get_price(b365, "1015", "1015"),
        "pin_over45":    get_price(pin,  "1016", "1016"),
        "pin_under45":   get_price(pin,  "1017", "1017"),
        "b365_over45":   get_price(b365, "1016", "1016"),
        "b365_under45":  get_price(b365, "1017", "1017"),
        "raw_data":      fixture,
    }


def run():
    print("=" * 55)
    print("  OddsPapi Odds ETL - WK2026 Pro Betting")
    print("=" * 55)

    wk_id = get_wk_id()

    print(f"\n[2/3] Odds ophalen (1 call)...")
    fixtures = api_get("odds-by-tournaments", {
        "tournamentIds": str(wk_id),
        "bookmakers":    BOOKMAKERS,
        "verbosity":     3,
    })
    print(f"      {len(fixtures)} fixtures ontvangen")

    print(f"\n[3/3] Opslaan in Supabase...")
    batch   = []
    total   = 0
    skipped = 0

    for f in fixtures:
        if not f.get("hasOdds"):
            skipped += 1
            continue
        batch.append(process(f))
        if len(batch) >= BATCH_SIZE:
            sb.from_("odds").upsert(batch, on_conflict="fixture_id").execute()
            total += len(batch)
            print(f"      {total} wedstrijden opgeslagen...")
            batch = []

    if batch:
        sb.from_("odds").upsert(batch, on_conflict="fixture_id").execute()
        total += len(batch)

    print(f"\n{'=' * 55}")
    print(f"  Klaar! {total} opgeslagen, {skipped} zonder odds")
    print("=" * 55)


if __name__ == "__main__":
    run()
