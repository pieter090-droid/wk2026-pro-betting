import os
import json
from supabase import create_client

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

root_dir = './data'
print(f"Start zoeken in: {os.path.abspath(root_dir)}")

found_any = False
for root, dirs, files in os.walk(root_dir):
    for file in files:
        file_path = os.path.join(root, file)
        # Debug: Print wat we tegenkomen
        print(f"Check bestand: {file_path}")
        
        if 'matches' in root and file.endswith('.json'):
            print(f"--> GEVONDEN: {file_path}")
            found_any = True
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sb.table("matches").insert({"match_data": data}).execute()
        else:
            # Debug: waarom wordt het overgeslagen?
            if file.endswith('.json'):
                print(f"    (Slaat over: 'matches' niet in pad '{root}')")

if not found_any:
    print("WAARSCHUWING: Geen enkel JSON-bestand in een 'matches' map gevonden!")
