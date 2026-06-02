import os
import json
from supabase import create_client

# Authenticatie
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Zoek in de gehele 'data' map
root_dir = './data'
count = 0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            
            # Sla de 'three-sixty' mappen over als je die nog niet nodig hebt
            if 'three-sixty' in file_path:
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    sb.table("matches").insert({"match_data": match_data}).execute()
                    count += 1
                except Exception as e:
                    print(f"Fout bij bestand {file}: {e}")

print(f"Klaar! Aantal bestanden geüpload: {count}")
