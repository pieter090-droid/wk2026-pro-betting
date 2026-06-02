import pandas as pd
import os
from supabase import create_client
from kaggle.api.kaggle_api_extended import KaggleApi

# 1. Authenticatie (deze secrets haalt hij veilig uit GitHub)
os.environ['KAGGLE_USERNAME'] = os.getenv('KAGGLE_USERNAME')
os.environ['KAGGLE_KEY'] = os.getenv('KAGGLE_KEY')
api = KaggleApi()
api.authenticate()

# 2. Download de dataset naar een tijdelijke map
api.dataset_download_files('saurabhshahane/statsbomb-football-data', path='./data', unzip=True)

# 3. Verbinden met Supabase
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# 4. CSV inladen en naar Supabase sturen
# Let op: zorg dat de bestandsnaam in de zip overeenkomt met wat hieronder staat
df = pd.read_csv("./data/matches.csv") 
data = df.to_dict(orient='records')
sb.table("matches").insert(data).execute()

print("Data succesvol naar de cloud-database gepusht!")
