import os
import json
from supabase import create_client

# Authenticatie
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

matches_dir = './data/data/matches'
print(f"Zoeken in map: {matches_dir}")

count = 0
for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # Upload naar Supabase
                    response = sb.table("matches").insert({"match_data": match_data}).execute()
                    count += 1
                except Exception as e:
                    print(f"Fout bij bestand {file}: {e}")

print(f"Klaar! Aantal bestanden verwerkt en geüpload: {count}")
