import os
import json
from kaggle.api.kaggle_api_extended import KaggleApi
from supabase import create_client

# 1. Haal secrets op
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise Exception("SUPABASE_URL of SUPABASE_KEY ontbreekt in de omgeving!")

# 2. Initialiseer client
sb = create_client(url, key)

# 3. Kaggle download
api = KaggleApi()
api.authenticate()
print("Downloaden van data...")
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# 4. Upload naar Supabase
matches_dir = './data/data/matches'
count = 0

print("Start met uploaden...")

for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # We sturen de data naar de tabel 'matches'
                    sb.from_("matches").insert({"match_data": match_data}).execute()
                    count += 1
                except Exception as e:
                    print(f"Fout bij {file}: {e}")

print(f"Klaar! Totaal {count} wedstrijden geüpload.")
