import os
import json
from supabase import create_client

# Authenticatie
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# We scannen vanaf de map './data' naar beneden
root_dir = './data'
count = 0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        # We zoeken alleen bestanden in de 'matches' map en die .json zijn
        if 'matches' in root and file.endswith('.json'):
            file_path = os.path.join(root, file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # Upload naar Supabase
                    sb.table("matches").insert({"match_data": match_data}).execute()
                    count += 1
                except Exception as e:
                    print(f"Fout bij bestand {file}: {e}")

print(f"Klaar! Aantal bestanden geüpload naar Supabase: {count}")
