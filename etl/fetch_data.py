import os
import json
from supabase import create_client

# Authenticatie
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Zoek direct in de juiste map
matches_dir = './data/data/matches'
count = 0

print("Start met uploaden van wedstrijddata...")

for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # Upload naar Supabase
                    sb.table("matches").insert({"match_data": match_data}).execute()
                    count += 1
                    if count % 10 == 0:
                        print(f"Al {count} wedstrijden geüpload...")
                except Exception as e:
                    print(f"Fout bij {file}: {e}")

print(f"Klaar! Totaal {count} wedstrijden succesvol in de database gezet.")
