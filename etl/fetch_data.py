import os
import json
from kaggle.api.kaggle_api_extended import KaggleApi
from supabase import create_client

# 1. Setup Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
sb = create_client(url, key)

# 2. Filters - Pas deze aan op basis van jouw exacte namen
# Check de 'competition_name' of 'home_team_name' in je data voor exacte spelling
TARGET_TEAMS = {"Netherlands", "Germany", "France", "Spain", "Brazil", "Argentina", "England", "Portugal", "USA", "Mexico", "Canada", "Belgium", "Italy"}
VALID_SEASONS = {"2022/2023", "2023/2024", "2024/2025", "2025/2026", "2022", "2023", "2024", "2025"}

matches_dir = './data/data/matches'
batch = []
batch_size = 50
count = 0

print("Start verwerking van mappenstructuur...")

# Loop door de mappen (competities)
for comp_id in os.listdir(matches_dir):
    comp_path = os.path.join(matches_dir, comp_id)
    if os.path.isdir(comp_path):
        
        # Loop door de bestanden (seizoenen per competitie)
        for season_file in os.listdir(comp_path):
            if season_file.endswith('.json'):
                file_path = os.path.join(comp_path, season_file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        # Elk bestand bevat een lijst met wedstrijden
                        season_matches = json.load(f)
                        
                        for m in season_matches:
                            # Haal relevante velden op
                            seizoen = m.get('season', {}).get('season_name')
                            home = m.get('home_team', {}).get('home_team_name')
                            away = m.get('away_team', {}).get('away_team_name')
                            
                            # Filter op seizoen EN of een doel-land speelt
                            if seizoen in VALID_SEASONS and (home in TARGET_TEAMS or away in TARGET_TEAMS):
                                batch.append({"match_data": m})
                                count += 1
                                
                                # Batch insert om Supabase-limieten en time-outs te voorkomen
                                if len(batch) >= batch_size:
                                    sb.from_("matches").insert(batch).execute()
                                    print(f"Batch geüpload. Totaal nu: {count}")
                                    batch = []
                                    
                    except Exception as e:
                        print(f"Fout bij {season_file}: {e}")

# Restant uploaden
if batch:
    sb.from_("matches").insert(batch).execute()

print(f"Klaar! Totaal {count} relevante wedstrijden in de database gezet.")
