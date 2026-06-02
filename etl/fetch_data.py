import os
import json
from supabase import create_client

# Authenticatie
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

root_dir = './data'
count = 0

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if 'matches' in root and file.endswith('.json'):
            file_path = os.path.join(root, file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # We printen de response om te zien wat er gebeurt
                    response = sb.table("matches").insert({"match_data": match_data}).execute()
                    print(f"Succes voor {file}")
                    count += 1
                except Exception as e:
                    print(f"CRITIEKE FOUT bij {file}: {e}")

print(f"Klaar! Totaal geüpload: {count}")
