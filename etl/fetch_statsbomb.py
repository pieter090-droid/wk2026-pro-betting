"""
WK2026 Pro Betting — StatsBomb ETL
Haalt data rechtstreeks op van de officiële StatsBomb GitHub repo
en laadt het in Supabase. Veilig te herhalen (geen duplicaten).
"""

import os
import time
import requests
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_KEY  = os.environ["SUPABASE_KEY"]   # service_role key
STATSBOMB_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
BATCH_SIZE    = 50
REQUEST_DELAY = 0.2   # seconden tussen GitHub requests (voorkomt rate limiting)

# ── Setup ─────────────────────────────────────────────────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def fetch_json(path: str) -> dict | list:
    """Haal JSON op van StatsBomb GitHub."""
    url = f"{STATSBOMB_BASE}/{path}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def upload_batch(batch: list) -> int:
    """Upload een batch naar Supabase. Geeft aantal geüploade rijen terug."""
    if not batch:
        return 0
    sb.from_("matches").upsert(batch, on_conflict="match_id").execute()
    return len(batch)


# ── Hoofdlogica ───────────────────────────────────────────────────────────────
def run():
    print("=" * 55)
    print("  StatsBomb ETL — WK2026 Pro Betting")
    print("=" * 55)

    # 1. Competities ophalen
    print("\n[1/3] Competities ophalen van StatsBomb...")
    competitions = fetch_json("competitions.json")
    print(f"      {len(competitions)} competitie-seizoen combinaties gevonden")

    # 2. Per competitie de wedstrijden ophalen
    print("\n[2/3] Wedstrijden ophalen en uploaden...")
    batch       = []
    total       = 0
    errors      = []
    seen_ids    = set()

    for i, comp in enumerate(competitions, 1):
        comp_id   = comp["competition_id"]
        season_id = comp["season_id"]
        comp_name = comp["competition_name"]
        season    = comp["season_name"]

        try:
            matches = fetch_json(f"matches/{comp_id}/{season_id}.json")
            time.sleep(REQUEST_DELAY)
        except requests.HTTPError as e:
            errors.append(f"{comp_name} {season}: {e}")
            continue
        except Exception as e:
            errors.append(f"{comp_name} {season}: {e}")
            continue

        nieuwe = 0
        for match in matches:
            match_id = match.get("match_id")
            if not match_id or match_id in seen_ids:
                continue
            seen_ids.add(match_id)
            batch.append({
                "match_id":   match_id,
                "match_data": match,
            })
            nieuwe += 1

            if len(batch) >= BATCH_SIZE:
                geupload = upload_batch(batch)
                total   += geupload
                print(f"      ✓ {total:>5} wedstrijden geüpload...")
                batch = []

        print(f"  [{i:>3}/{len(competitions)}] {comp_name} {season} — {nieuwe} wedstrijden")

    # Resterende batch uploaden
    if batch:
        total += upload_batch(batch)

    # 3. Samenvatting
    print("\n[3/3] Klaar!")
    print(f"      Totaal geüpload / bijgewerkt: {total} wedstrijden")

    if errors:
        print(f"\n  ⚠ {len(errors)} competities overgeslagen:")
        for err in errors:
            print(f"    - {err}")

    print("\nControleer je data met:")
    print("  SELECT home_team, away_team, home_score, away_score")
    print("  FROM view_matches_summary LIMIT 10;")
    print("=" * 55)


if __name__ == "__main__":
    run()
