import os
from kaggle.api.kaggle_api_extended import KaggleApi

# Authenticatie
api = KaggleApi()
api.authenticate()

# Download
print("Downloaden...")
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# Detectie: Loop door alles wat in ./data staat, ongeacht extensie
print("--- START BESTANDSLIJST ---")
for root, dirs, files in os.walk('./data'):
    for file in files:
        print(f"Gevonden: {os.path.join(root, file)}")
print("--- EINDE BESTANDSLIJST ---")
