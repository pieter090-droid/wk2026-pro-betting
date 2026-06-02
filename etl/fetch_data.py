import os
import json
import requests
from supabase import create_client

# 1. Setup
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

def fetch_json(path):
    r = requests.get(f"{BASE_URL}/{path}")
    r.raise_for_status()
    return r.json()

# 2. Haal alle competities op
print("Competities ophalen...")
competitions = fetch_json("competitions.json")
print(f"{len(competitions)} competities gevonden")

# 3. Per competitie, per seizoen → wedstrijden ophalen
batch = []
batch_size = 50
seen_match_ids = set()
total = 0

for comp in competitions:
    competition_id = comp["competition_id"]
    season_id = comp["season_id"]
    competition_name = comp["competition_name"]
    season_name = comp["season_name"]

    try:
        matches = fetch_json(f"matches/{competition_id}/{season_id}.json")
    except Exception as e:
        print(f"Overgeslagen: {competition_name} {season_name} — {e}")
        continue

    for match in matches:
        match_id = match.get("match_id")
        if match_id in seen_match_ids:
            continue
        seen_match_ids.add(match_id)

        batch.append({"match_data": match})

        if len(batch) >= batch_size:
            try:
                sb.from_("matches").upsert(
                    batch,
                    on_conflict="match_data->>'match_id'"  # voorkom duplicaten
                ).execute()
                total += len(batch)
                print(f"{total} wedstrijden geüpload...")
            except Exception as e:
                print(f"Upload fout: {e}")
            batch = []

# Restant
if batch:
    sb.from_("matches").upsert(batch).execute()
    total += len(batch)

print(f"Klaar! {total} wedstrijden totaal geüpload.")
