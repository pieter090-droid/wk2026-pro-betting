import os
import json
from supabase import create_client

# Authenticatie
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Loop door de mappenstructuur die we in de logs zagen
matches_dir = './data/data/matches'
for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # We stoppen het hele JSON-object in de 'match_data' kolom
                    sb.table("matches").insert({"match_data": match_data}).execute()
                except Exception as e:
                    print(f"Kon {file} niet verwerken: {e}")

print("Upload naar database voltooid!")
