import shutil
from pathlib import Path
import kagglehub
import pandas as pd

#Letölti a 2023-as F1 szezon nyers adatait a Kaggle-ről
DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)

forras = Path(kagglehub.dataset_download("juampimgi/formula-1-season-2023"))
quali_forras = Path(kagglehub.dataset_download("jtrotman/formula-1-race-data", path="qualifying.csv"))
print("Letöltve ide:", forras, quali_forras)

for f in sorted(forras.rglob("*.csv")):
    shutil.copy(f, DATA / f.name)
    print(f"Másolva: {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")

races = pd.read_csv(kagglehub.dataset_download("jtrotman/formula-1-race-data", path="races.csv"), na_values=["\\N"])
races = races[races["year"] == 2023][["raceId", "round", "name"]].sort_values("round")
races.to_csv(DATA / "races_2023.csv", index=False)
print(races.to_string(index=False))          # itt látod, melyik raceId melyik futam

q = pd.read_csv(kagglehub.dataset_download("jtrotman/formula-1-race-data", path="qualifying.csv"), na_values=["\\N"])
q = q[q["raceId"].isin(races["raceId"])]
q.to_csv(DATA / "qualifying.csv", index=False)
print(f"qualifying.csv: {len(q)} sor, {q['raceId'].nunique()} futam (22 kell)")