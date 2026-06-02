import os
from kaggle.api.kaggle_api_extended import KaggleApi

# 1. Authenticatie
api = KaggleApi()
api.authenticate()

# 2. Download en expliciet uitpakken
print("Start download...")
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# 3. Wacht tot we zeker weten dat er bestanden zijn
print("Bestanden in huidige map:", os.listdir('.'))
if os.path.exists('./data'):
    print("Inhoud van ./data:", os.listdir('./data'))
else:
    print("Map ./data bestaat niet!")
