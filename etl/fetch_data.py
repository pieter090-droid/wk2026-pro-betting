import os
import json
from kaggle.api.kaggle_api_extended import KaggleApi
from supabase import create_client

# Instellingen
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

# Filters
# Voeg hier landen toe die voor jou relevant zijn
TARGET_TEAMS = {"Netherlands", "Germany", "France", "Spain", "Brazil", "Argentina", "England", "Portugal", "USA", "Mexico", "Canada", "Belgium", "Italy"}
# Seizoenen van de laatste 4 jaar
VALID_SEASONS = {"2022/2023", "2023/2024", "2024/2025", "2025/2026", "2022", "2023", "2024", "2025"}

matches_dir = './data/data/matches'
batch = []
batch_size = 50
count = 0

print("Start verwerking (gefilterd op WK-landen en recente seizoenen)...")

for root, dirs, files in os.walk(matches_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    match_data = json.load(f)
                    m = match_data[0] # StatsBomb data is een lijst, pak het eerste object
                    
                    seizoen = m.get('season', {}).get('season_name')
                    home = m.get('home_team', {}).get('home_team_name')
                    away = m.get('away_team', {}).get('away_team_name')
                    
                    # Filter: Is het een recent seizoen EN speelt een van onze doel-landen?
                    if seizoen in VALID_SEASONS and (home in TARGET_TEAMS or away in TARGET_TEAMS):
                        batch.append({"match_data": match_data})
                        count += 1
                        
                        if len(batch) >= batch_size:
                            sb.from_("matches").insert(batch).execute()
                            batch = []
                            print(f"Uploaded {count} relevante wedstrijden...")
                except Exception as e:
                    continue

# Resterende batch uploaden
if batch:
    sb.from_("matches").insert(batch).execute()

print(f"Klaar! {count} relevante wedstrijden in de database gezet.")
