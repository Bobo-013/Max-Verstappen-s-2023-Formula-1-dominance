import shutil
from pathlib import Path
import kagglehub

#Letölti a 2023-as F1 szezon nyers adatait a Kaggle-ről
DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)

forras = Path(kagglehub.dataset_download("juampimgi/formula-1-season-2023"))
print("Letöltve ide:", forras)

for f in sorted(forras.rglob("*.csv")):
    shutil.copy(f, DATA / f.name)
    print(f"Másolva: {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")