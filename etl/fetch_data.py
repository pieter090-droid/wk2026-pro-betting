import os
from kaggle.api.kaggle_api_extended import KaggleApi

# Authenticatie
os.environ['KAGGLE_USERNAME'] = os.getenv('KAGGLE_USERNAME')
os.environ['KAGGLE_KEY'] = os.getenv('KAGGLE_KEY')
api = KaggleApi()
api.authenticate()

# Download de dataset
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# HIER zie je de mappen en bestanden in de logs
print("--- INHOUD VAN MAP 'data' ---")
for root, dirs, files in os.walk('./data'):
    for name in files:
        print(os.path.join(root, name))
print("-----------------------------")

# DIT IS HET DEEL DAT NU NOG KAN FALEN
# Pas dit pas aan als je de echte naam hierboven in de logs ziet!
# df = pd.read_csv("./data/echte_naam.csv")
