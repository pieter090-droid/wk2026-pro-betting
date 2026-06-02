import os
import json
from supabase import create_client

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

root_dir = './data'
count = 0

print("Begin met zoeken naar ALLE .json bestanden...")

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            print(f"Verwerken: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    # We proberen de insert
                    sb.table("matches").insert({"match_data": match_data}).execute()
                    count += 1
                except Exception as e:
                    print(f"Fout bij {file_path}: {e}")

print(f"Klaar! Totaal geüpload: {count}")
