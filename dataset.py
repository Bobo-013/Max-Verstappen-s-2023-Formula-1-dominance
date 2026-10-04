import shutil
from pathlib import Path
import pandas as pd

import kagglehub

cel = Path("data")
cel.mkdir(exist_ok=True)

#forras = Path(kagglehub.dataset_download("juampimgi/formula-1-season-2023"))

#for f in forras.glob("*.csv"):
#    shutil.copy(f, cel / f.name)
#    print("Másolva:", f.name)

#print("Kész, fájlok itt:", cel.resolve())

DATA = Path("data")
OUT = DATA / "processed"
OUT.mkdir(exist_ok=True)

# ---------- Betöltés (csak a szükséges oszlopok) ----------
cols = ["Abbreviation", "FullName", "TeamName", "TeamColor", "Position",
        "GridPosition", "Points", "RoundNumber", "EventName"]
race = pd.read_csv(DATA / "Results.csv", usecols=cols)
sprint = pd.read_csv(DATA / "Sprint_Results.csv", usecols=cols)
events = pd.read_csv(DATA / "Events.csv",
                     usecols=["RoundNumber", "Country", "Location", "EventName", "EventDate"])

rounds = sorted(events["RoundNumber"].unique())

# ---------- Pontok (futam + sprint együtt) ----------
all_pts = pd.concat([race, sprint], ignore_index=True)

def cumulative(by):
    per_round = (all_pts.pivot_table(index="RoundNumber", columns=by,
                                     values="Points", aggfunc="sum", fill_value=0)
                 .reindex(rounds, fill_value=0))
    return per_round.cumsum()

driver_cum = cumulative("Abbreviation")
team_cum = cumulative("TeamName")

driver_cum.to_csv(OUT / "driver_cumulative_points.csv")
team_cum.to_csv(OUT / "team_cumulative_points.csv")

# ---------- Pilóták és csapatok adatai (név, csapat, szín) ----------
drivers = (race.sort_values("RoundNumber")
           .drop_duplicates("Abbreviation", keep="last")
           [["Abbreviation", "FullName", "TeamName", "TeamColor"]])
drivers["TotalPoints"] = drivers["Abbreviation"].map(driver_cum.iloc[-1])
drivers = drivers.sort_values("TotalPoints", ascending=False)

# Holtverseny pontok javítása
pos = (race.dropna(subset=["Position"])
       .assign(Position=lambda d: d["Position"].astype(int))
       .pivot_table(index="Abbreviation", columns="Position",
                    values="RoundNumber", aggfunc="count", fill_value=0)
       .reindex(columns=range(1, 21), fill_value=0))

drivers = drivers.join(pos, on="Abbreviation")
drivers = drivers.sort_values(["TotalPoints"] + list(range(1, 21)), ascending=False)
drivers = drivers[["Abbreviation", "FullName", "TeamName", "TeamColor", "TotalPoints"]]

drivers.to_csv(OUT / "drivers.csv", index=False)

teams = (race.drop_duplicates("TeamName")[["TeamName", "TeamColor"]]
         .assign(TotalPoints=lambda d: d["TeamName"].map(team_cum.iloc[-1]))
         .sort_values("TotalPoints", ascending=False))
teams.to_csv(OUT / "teams.csv", index=False)

# ---------- Futamok koordinátákkal (földgömbhöz) ----------
coords = {
    "Bahrain Grand Prix": (26.0325, 50.5106),
    "Saudi Arabian Grand Prix": (21.6319, 39.1044),
    "Australian Grand Prix": (-37.8497, 144.9680),
    "Azerbaijan Grand Prix": (40.3725, 49.8533),
    "Miami Grand Prix": (25.9581, -80.2389),
    "Monaco Grand Prix": (43.7347, 7.4206),
    "Spanish Grand Prix": (41.5700, 2.2611),
    "Canadian Grand Prix": (45.5000, -73.5228),
    "Austrian Grand Prix": (47.2197, 14.7647),
    "British Grand Prix": (52.0786, -1.0169),
    "Hungarian Grand Prix": (47.5789, 19.2486),
    "Belgian Grand Prix": (50.4372, 5.9714),
    "Dutch Grand Prix": (52.3888, 4.5409),
    "Italian Grand Prix": (45.6156, 9.2811),
    "Singapore Grand Prix": (1.2914, 103.8640),
    "Japanese Grand Prix": (34.8431, 136.5410),
    "Qatar Grand Prix": (25.4900, 51.4542),
    "United States Grand Prix": (30.1328, -97.6411),
    "Mexico City Grand Prix": (19.4042, -99.0907),
    "São Paulo Grand Prix": (-23.7036, -46.6997),
    "Las Vegas Grand Prix": (36.1147, -115.1728),
    "Abu Dhabi Grand Prix": (24.4672, 54.6031),
}
events["Lat"] = events["EventName"].map(lambda n: coords.get(n, (None, None))[0])
events["Lon"] = events["EventName"].map(lambda n: coords.get(n, (None, None))[1])

winners = (race[race["Position"] == 1][["RoundNumber", "FullName"]]
           .rename(columns={"FullName": "Winner"}))
events = events.merge(winners, on="RoundNumber", how="left")
events.to_csv(OUT / "events.csv", index=False)

missing = events[events["Lat"].isna()]["EventName"].tolist()
if missing:
    print("FIGYELEM, nincs koordináta ezekhez:", missing)

# ---------- Verstappen szezonstatisztikák ----------
ver = race[race["Abbreviation"] == "VER"]
fl = pd.read_csv(DATA / "Fastest_Laps.csv", usecols=["Driver", "RoundNumber"])
laps = pd.read_csv(DATA / "Laps.csv", usecols=["Driver"])

stats = {
    "races": len(rounds),
    "wins": int((ver["Position"] == 1).sum()),
    "podiums": int(ver["Position"].isin([1, 2, 3]).sum()),
    "poles": int((ver["GridPosition"] == 1).sum()),   # közelítés: a rajtrács első helye
    "fastest_laps": int((fl["Driver"] == "VER").sum()),
    "laps_completed": int((laps["Driver"] == "VER").sum()),
    "points": float(driver_cum["VER"].iloc[-1]),
}
pd.Series(stats).to_csv(OUT / "verstappen_stats.csv", header=["value"])

# ---------- Ellenőrzés ----------
print("\nTOP 5 pilóta:")
print(drivers.head(5)[["FullName", "TeamName", "TotalPoints"]].to_string(index=False))
print("\nTOP 5 csapat:")
print(teams.head(5)[["TeamName", "TotalPoints"]].to_string(index=False))
print("\nVerstappen:", stats)
print("\nKész, a fájlok itt vannak:", OUT.resolve())