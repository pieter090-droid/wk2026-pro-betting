import os
from kaggle.api.kaggle_api_extended import KaggleApi

# Authenticatie
os.environ['KAGGLE_USERNAME'] = os.getenv('KAGGLE_USERNAME')
os.environ['KAGGLE_KEY'] = os.getenv('KAGGLE_KEY')
api = KaggleApi()
api.authenticate()

# Download de dataset
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# KIJK WAAR HET BESTAND IS
print("Bestanden gevonden in map 'data':")
for file in os.listdir('./data'):
    print(file)
