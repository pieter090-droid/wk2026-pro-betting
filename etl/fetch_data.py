import os
import json
from kaggle.api.kaggle_api_extended import KaggleApi
from supabase import create_client

# 1. Setup
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

# 2. Download
print("Downloaden van data...")
api = KaggleApi()
api.authenticate()
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# 3. Upload (Simpele loop die alles pakt)
matches_dir = './data/data/matches'
batch = []
batch_size = 50 

print("Start met uploaden van alle gevonden wedstrijden...")

for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    
                    # De StatsBomb bestanden bevatten vaak een lijst, 
                    # we voegen ze toe aan onze batch
                    if isinstance(match_data, list):
                        for m in match_data:
                            batch.append({"match_data": m})
                    else:
                        batch.append({"match_data": match_data})
                    
                    if len(batch) >= batch_size:
                        sb.from_("matches").insert(batch).execute()
                        print(f"Batch geüpload...")
                        batch = []
                except Exception as e:
                    print(f"Fout bij {file}: {e}")

# Restant
if batch:
    sb.from_("matches").insert(batch).execute()

print("Klaar!")
