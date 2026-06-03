"""
WK2026 Pro Betting — OddsPapi Odds ETL
Haalt alle WK 2026 wedstrijden + odds op via OddsPapi.
1 call per dag voor alle markets: 1X2, BTTS, O/U 1.5/2.5/3.5/4.5
Slaat op in Supabase odds tabel.
"""

import os
import time
import requests
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
ODDSPAPI_KEY    = os.environ["ODDSPAPI_KEY"]

BASE_URL        = "https://api.oddspapi.io/v4"
SPORT_ID        = 10        # Soccer/Football
BATCH_SIZE      = 50

# Bookmakers die we opslaan
BOOKMAKERS      = "pinnacle,bet365"

# Market ID mapping
MARKET_IDS = {
    "1x2":      "101",
    "btts":     "104",
    "over15":   "1012",
    "under15":  "1013",
    "over25":   "1010",
    "under25":  "1011",
    "over35":   "1014",
    "under35":  "1015",
    "over45":   "1016",
    "under45":  "1017",
}

# Outcome IDs per market
OUTCOME_IDS = {
    "101":  {"home": "101", "draw": "102", "away": "103"},
    "104":  {"yes":  "104", "no":   "105"},
    "1012": {"over": "1012"},
    "1013": {"under":"1013"},
    "1010": {"over": "1010"},
    "1011": {"under":"1011"},
    "1014": {"over": "1014"},
    "1015": {"under":"1015"},
    "1016": {"over": "1016"},
    "1017": {"under":"1017"},
}

# ── Setup ─────────────────────────────────────────────────────────────────────
sb      = create_client(SUPABASE_URL, SUPABASE_KEY)
session = requests.Session()
session.headers.update({"Content-Type": "application/json"})


def api_get(path: str, params: dict) -> dict | list:
    params["apiKey"] = ODDSPAPI_KEY
    params["oddsFormat"] = "decimal"
    r = session.get(f"{BASE_URL}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Stap 1: WK 2026 tournament ID ophalen ────────────────────────────────────

def get_wk_tournament_id() -> int:
    """Zoek het WK 2026 tournament ID op via de tournaments endpoint."""
    print("[1/3] WK 2026 tournament ID ophalen...")
    tournaments = api_get("tournaments", {"sportId": SPORT_ID})

    # Zoek op naam
    keywords = ["world cup", "fifa", "wk", "mundial"]
    for t in tournaments:
        name = t.get("tournamentName", "").lower()
        if any(kw in name for kw in keywords):
            tid = t["tournamentId"]
            tname = t["tournamentName"]
            print(f"      Gevonden: {tname} (ID: {tid})")
            return tid

    # Als niet gevonden, print alle toernooien
    print("      ⚠ WK niet automatisch gevonden. Beschikbare toernooien:")
    for t in tournaments[:20]:
        print(f"        {t['tournamentId']}: {t['tournamentName']}")
    raise ValueError("Kon WK 2026 tournament ID niet vinden. Stel ODDSPAPI_WK_ID in als env var.")


# ── Stap 2: Odds ophalen ──────────────────────────────────────────────────────

def extract_price(bm_data: dict, market_id: str, outcome_id: str) -> float | None:
    """Haal een prijs op uit de geneste OddsPapi structuur."""
    try:
        market = bm_data.get("markets", {}).get(market_id)
        if not market:
            return None
        outcome = market.get("outcomes", {}).get(outcome_id)
        if not outcome:
            return None
        players = outcome.get("players", {})
        if not players:
            return None
        # Pak de eerste actieve speler
        for player in players.values():
            if player.get("active"):
                return player.get("price")
        return None
    except Exception:
        return None


def process_fixture(fixture: dict) -> dict | None:
    """Verwerk één fixture naar ons database formaat."""
    fixture_id = fixture.get("fixtureId")
    if not fixture_id:
        return None

    bm_odds = fixture.get("bookmakerOdds", {})
    pin  = bm_odds.get("pinnacle", {})
    b365 = bm_odds.get("bet365", {})

    # Participant namen uit fixture (als beschikbaar)
    home_team = fixture.get("participant1Name", "")
    away_team = fixture.get("participant2Name", "")

    record = {
        "fixture_id":   fixture_id,
        "home_team":    home_team,
        "away_team":    away_team,
        "start_time":   fixture.get("startTime"),
        "tournament_id": fixture.get("tournamentId"),
        "status_id":    fixture.get("statusId", 0),

        # Pinnacle 1X2
        "pin_home":     extract_price(pin,  "101", "101"),
        "pin_draw":     extract_price(pin,  "101", "102"),
        "pin_away":     extract_price(pin,  "101", "103"),

        # Bet365 1X2
        "b365_home":    extract_price(b365, "101", "101"),
        "b365_draw":    extract_price(b365, "101", "102"),
        "b365_away":    extract_price(b365, "101", "103"),

        # Pinnacle BTTS
        "pin_btts_yes": extract_price(pin,  "104", "104"),
        "pin_btts_no":  extract_price(pin,  "104", "105"),

        # Bet365 BTTS
        "b365_btts_yes": extract_price(b365, "104", "104"),
        "b365_btts_no":  extract_price(b365, "104", "105"),

        # Over/Under 1.5
        "pin_over15":   extract_price(pin,  "1012", "1012"),
        "pin_under15":  extract_price(pin,  "1013", "1013"),
        "b365_over15":  extract_price(b365, "1012", "1012"),
        "b365_under15": extract_price(b365, "1013", "1013"),

        # Over/Under 2.5
        "pin_over25":   extract_price(pin,  "1010", "1010"),
        "pin_under25":  extract_price(pin,  "1011", "1011"),
        "b365_over25":  extract_price(b365, "1010", "1010"),
        "b365_under25": extract_price(b365, "1011", "1011"),

        # Over/Under 3.5
        "pin_over35":   extract_price(pin,  "1014", "1014"),
        "pin_under35":  extract_price(pin,  "1015", "1015"),
        "b365_over35":  extract_price(b365, "1014", "1014"),
        "b365_under35": extract_price(b365, "1015", "1015"),

        # Over/Under 4.5
        "pin_over45":   extract_price(pin,  "1016", "1016"),
        "pin_under45":  extract_price(pin,  "1017", "1017"),
        "b365_over45":  extract_price(b365, "1016", "1016"),
        "b365_under45": extract_price(b365, "1017", "1017"),

        # Ruwe data
        "raw_data":     fixture,
    }

    return record


# ── Stap 3: Opslaan in Supabase ───────────────────────────────────────────────

def upsert_batch(records: list) -> int:
    if not records:
        return 0
    sb.from_("odds").upsert(records, on_conflict="fixture_id").execute()
    return len(records)


# ── Hoofdlogica ───────────────────────────────────────────────────────────────

def run():
    print("=" * 55)
    print("  OddsPapi Odds ETL — WK2026 Pro Betting")
    print("=" * 55)

    # Tournament ID ophalen (of uit env var)
    # GitHub maskeert secrets als '***' in logs maar geeft ze correct door
    # Toch valideren voor het geval het secret niet ingesteld is
    wk_id_raw = os.environ.get("ODDSPAPI_WK_ID", "").strip()
    if wk_id_raw and wk_id_raw.isdigit():
        wk_id = int(wk_id_raw)
        print(f"[1/3] WK tournament ID uit env: {wk_id}")
    else:
        if wk_id_raw:
            print(f"[1/3] ODDSPAPI_WK_ID niet geldig, automatisch zoeken...")
        wk_id = get_wk_tournament_id()

    # Alle odds ophalen — 1 call
    print(f"\n[2/3] Odds ophalen voor tournament {wk_id}...")
    print(f"      Bookmakers: {BOOKMAKERS}")
    print(f"      Markets: 1X2, BTTS, O/U 1.5/2.5/3.5/4.5")

    fixtures = api_get("odds-by-tournaments", {
        "tournamentIds": str(wk_id),
        "bookmakers":    BOOKMAKERS,
        "verbosity":     3,
    })

    print(f"      {len(fixtures)} fixtures ontvangen")

    # Verwerken
    print(f"\n[3/3] Opslaan in Supabase...")
    batch   = []
    total   = 0
    no_odds = 0

    for fixture in fixtures:
        if not fixture.get("hasOdds"):
            no_odds += 1
            continue

        record = process_fixture(fixture)
        if not record:
            continue

        batch.append(record)

        if len(batch) >= BATCH_SIZE:
            total += upsert_batch(batch)
            print(f"      ✓ {total} wedstrijden opgeslagen...")
            batch = []

    if batch:
        total += upsert_batch(batch)

    # Samenvatting
    print(f"\n{'=' * 55}")
    print(f"  Klaar!")
    print(f"  Opgeslagen:    {total} wedstrijden met odds")
    print(f"  Zonder odds:   {no_odds} wedstrijden")
    print(f"  API calls gebruikt: 2 (1 tournaments + 1 odds)")
    print(f"\n  Check met:")
    print(f"  SELECT home_team, away_team, pin_home, pin_draw,")
    print(f"         pin_away, pin_over25, pin_btts_yes")
    print(f"  FROM view_odds_summary LIMIT 10;")
    print("=" * 55)


if __name__ == "__main__":
    run()
