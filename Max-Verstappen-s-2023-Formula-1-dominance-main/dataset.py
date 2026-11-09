from pathlib import Path
 
import numpy as np
import pandas as pd
 
# 1. Beállítások és segédfüggvények
DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "processed"
OUT.mkdir(exist_ok=True)
 
 
# Másodpercből köridő szöveg
def fmt_sec(s):
    m = int(s // 60)
    return f"{m}:{s - 60 * m:06.3f}"
 
 
# 2. Betöltés
cols = ["Abbreviation", "FullName", "TeamName", "TeamColor", "Position",
        "GridPosition", "Points", "RoundNumber", "EventName"]
race = pd.read_csv(DATA / "Results.csv", usecols=cols)
sprint = pd.read_csv(DATA / "Sprint_Results.csv", usecols=cols)
events = pd.read_csv(DATA / "Events.csv",
                     usecols=["RoundNumber", "Country", "Location", "EventName", "EventDate"])
 
rounds = sorted(events["RoundNumber"].unique())
 
# A köröket egyszer töltjük be, a script minden része ezt használja
LAP_COLS = ["RoundNumber", "DriverNumber", "Driver", "LapNumber",
            "LapStartTime", "Time", "LapTime",
            "Stint", "Compound", "TyreLife", "TrackStatus"]
laps_all = pd.read_csv(DATA / "Laps.csv", usecols=LAP_COLS,
                       dtype={"TrackStatus": str})
laps_all = laps_all.dropna(subset=["RoundNumber", "DriverNumber", "LapNumber"]).copy()
for c in ["RoundNumber", "DriverNumber", "LapNumber"]:
    laps_all[c] = laps_all[c].astype(int)
 
# Az időpontokat másodpercre alakítja
laps_all["LapStart"] = pd.to_timedelta(laps_all["LapStartTime"]).dt.total_seconds()
laps_all["LapEnd"] = pd.to_timedelta(laps_all["Time"]).dt.total_seconds()
laps_all["LapTimeSec"] = pd.to_timedelta(laps_all["LapTime"]).dt.total_seconds()
 
 
# 3. Kiválasztott pilóták: futamonként a top 3 + Verstappen
def tel_drivers(rn):
    r = race[race["RoundNumber"] == rn].copy()
    r["Position"] = pd.to_numeric(r["Position"], errors="coerce")
    top3 = r.sort_values("Position").head(3)["Abbreviation"].tolist()
    return set(top3) | {"VER"}
 
 
top_by_round = {int(rn): tel_drivers(rn) for rn in rounds}
 
 
# 4. Pontok, pilóták, csapatok

# Futam + sprint pontjai együtt
all_pts = pd.concat([race, sprint], ignore_index=True)
 
 
# Kumulált pontszám futamonként. A "by" lehet "Abbreviation" (pilóta)
# vagy "TeamName" (csapat). Eredmény: sorok = futamok, oszlopok = pilóták/csapatok.
def cumulative(by):
    per_round = (all_pts.pivot_table(index="RoundNumber", columns=by,
                                     values="Points", aggfunc="sum", fill_value=0)
                 .reindex(rounds, fill_value=0))
    return per_round.cumsum()
 
 
driver_cum = cumulative("Abbreviation")
team_cum = cumulative("TeamName")
driver_cum.to_csv(OUT / "driver_cumulative_points.csv")
team_cum.to_csv(OUT / "team_cumulative_points.csv")
 
# Pilóták: név, csapat, szín, összpont
drivers = (race.sort_values("RoundNumber")
           .drop_duplicates("Abbreviation", keep="last")
           [["Abbreviation", "FullName", "TeamName", "TeamColor"]])
drivers["TotalPoints"] = drivers["Abbreviation"].map(driver_cum.iloc[-1])
drivers = drivers.sort_values("TotalPoints", ascending=False)
 
# Holtverseny kezelése
pos = (race.dropna(subset=["Position"])
       .assign(Position=lambda d: d["Position"].astype(int))
       .pivot_table(index="Abbreviation", columns="Position",
                    values="RoundNumber", aggfunc="count", fill_value=0)
       .reindex(columns=range(1, 21), fill_value=0))
 
drivers = drivers.join(pos, on="Abbreviation")
drivers = drivers.sort_values(["TotalPoints"] + list(range(1, 21)), ascending=False)
drivers = drivers[["Abbreviation", "FullName", "TeamName", "TeamColor", "TotalPoints"]]
drivers.to_csv(OUT / "drivers.csv", index=False)
 
# Csapatok: név, szín, összpont
teams = (race.drop_duplicates("TeamName")[["TeamName", "TeamColor"]]
         .assign(TotalPoints=lambda d: d["TeamName"].map(team_cum.iloc[-1]))
         .sort_values("TotalPoints", ascending=False))
teams.to_csv(OUT / "teams.csv", index=False)
 
 
# 5. Futamok koordinátákkal (a földgömbhöz) és győztesekkel
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
 
# Futamgyőztes hozzáfűzése
winners = (race[race["Position"] == 1][["RoundNumber", "FullName"]]
           .rename(columns={"FullName": "Winner"}))
events = events.merge(winners, on="RoundNumber", how="left")
events.to_csv(OUT / "events.csv", index=False)
 
missing = events[events["Lat"].isna()]["EventName"].tolist()
if missing:
    print("FIGYELEM, nincs koordináta ezekhez:", missing)
 
 
# 6. Verstappen szezonstatisztikák
ver = race[race["Abbreviation"] == "VER"]
fl = pd.read_csv(DATA / "Fastest_Laps.csv", usecols=["Driver", "RoundNumber"])
 
stats = {
    "races": len(rounds),
    "wins": int((ver["Position"] == 1).sum()),
    "podiums": int(ver["Position"].isin([1, 2, 3]).sum()),
    "poles": int((ver["GridPosition"] == 1).sum()),   # közelítés: a rajtrács első helye
    "fastest_laps": int((fl["Driver"] == "VER").sum()),
    "laps_completed": int((laps_all["Driver"] == "VER").sum()),
    "points": float(driver_cum["VER"].iloc[-1]),
}
pd.Series(stats).to_csv(OUT / "verstappen_stats.csv", header=["value"])
 
 
# 7. Gumistintek és futamfelfüggesztések

# TrackStatus kódok: 1 = zöld, 2 = sárga, 4 = biztonsági autó,
# 5 = piros zászló, 6/7 = VSC.
FLAG_PRIORITY = [("5", "Piros zászló"), ("4", "Biztonsági autó"),
                 ("6", "VSC"), ("7", "VSC"), ("2", "Sárga zászló")]
 
 
# A kör állapotkódjaiból kiválasztja a legsúlyosabb
def lap_flag(codes):
    for code, label in FLAG_PRIORITY:
        if code in codes:
            return label
    return None
 
 
# Gumistintek: gumitípus, kezdő/záró kör, a gumi kezdeti kora.
selected = pd.MultiIndex.from_frame(laps_all[["RoundNumber", "Driver"]]).isin(
    {(rn, d) for rn, ds in top_by_round.items() for d in ds})
st = (laps_all[selected].dropna(subset=["Stint"])
      .sort_values(["RoundNumber", "Driver", "LapNumber"]))
 
stint_rows = []
for (rn, drv, stint), g in st.groupby(["RoundNumber", "Driver", "Stint"]):
    comp = g["Compound"].dropna()
    age = g["TyreLife"].dropna()
    stint_rows.append({
        "RoundNumber": int(rn), "Driver": drv, "Stint": int(stint),
        "Compound": comp.iloc[0] if not comp.empty else "UNKNOWN",
        "StartLap": int(g["LapNumber"].min()),
        "EndLap": int(g["LapNumber"].max()),
        "StartAge": int(age.iloc[0]) if not age.empty else None,
    })
pd.DataFrame(stint_rows).to_csv(OUT / "stints.csv", index=False)
 
# Futamfelfüggesztések körönként
status = (laps_all.dropna(subset=["TrackStatus"])
          .groupby(["RoundNumber", "LapNumber"])["TrackStatus"].agg("".join))
flag_rows = [{"RoundNumber": int(rn), "LapNumber": int(lap), "Status": lap_flag(codes)}
             for (rn, lap), codes in status.items() if lap_flag(codes)]
pd.DataFrame(flag_rows, columns=["RoundNumber", "LapNumber", "Status"]).to_csv(
    OUT / "track_status.csv", index=False)
 
 
# 8. Telemetria: a kiválasztott pilóták leggyorsabb teljes köre
TEL_SRC = DATA / "Telemetry.csv"
TEL_OUT = OUT / "telemetry"
TEL_OUT.mkdir(exist_ok=True)
TEL_INDEX = OUT / "telemetry_index.csv"
 

num2abbr = (laps_all.drop_duplicates(["RoundNumber", "DriverNumber"])
            .set_index(["RoundNumber", "DriverNumber"])["Driver"].to_dict())
wanted = {k for k, abbr in num2abbr.items() if abbr in top_by_round.get(k[0], set())}
 
# A kiválasztott pilóták sorait tartjuk meg.
head = pd.read_csv(TEL_SRC, nrows=3)
 
drv_col = next(c for c in ["DriverNumber", "Driver", "Drivernumber", "Car"]
               if c in head.columns)
tel_usecols = [c for c in ["Date", "RPM", "Speed", "nGear", "Throttle", "Brake",
                           "DRS", "SessionTime", "RoundNumber", drv_col]
               if c in head.columns]
 
parts = {}   # (futam, rajtszám) -> darabok listája
for chunk in pd.read_csv(TEL_SRC, usecols=tel_usecols, chunksize=500_000):
    chunk = chunk.rename(columns={drv_col: "DriverNumber"})
    chunk = chunk.dropna(subset=["RoundNumber", "DriverNumber"])
    chunk["RoundNumber"] = chunk["RoundNumber"].astype(int)
    chunk["DriverNumber"] = chunk["DriverNumber"].astype(int)
    mask = pd.MultiIndex.from_frame(chunk[["RoundNumber", "DriverNumber"]]).isin(wanted)
    for key, g in chunk[mask].groupby(["RoundNumber", "DriverNumber"]):
        parts.setdefault(key, []).append(g)
 
# 8/2. Pilótánként: körszám hozzárendelése, a leggyorsabb teljes kör
tel_rows = []
for (rn, num), frames in sorted(parts.items()):
    abbr = num2abbr[(rn, num)] 
    tel = pd.concat(frames, ignore_index=True)
    tel["SessionTime"] = pd.to_timedelta(tel["SessionTime"]).dt.total_seconds()
    tel = tel.dropna(subset=["SessionTime"]).sort_values("SessionTime")
 
    # A pilóta körei
    dl = (laps_all[(laps_all["RoundNumber"] == rn) & (laps_all["DriverNumber"] == num)]
          .sort_values("LapNumber")[["LapNumber", "LapStart", "LapEnd", "LapTimeSec"]]
          .copy())
    dl["LapStart"] = dl["LapStart"].fillna(dl["LapEnd"].shift(1))
    dl.loc[dl["LapNumber"] == dl["LapNumber"].min(), "LapStart"] = \
        dl.loc[dl["LapNumber"] == dl["LapNumber"].min(), "LapStart"].fillna(0)
    dl = dl.dropna(subset=["LapStart", "LapEnd"]).sort_values("LapStart")
    if dl.empty:
        continue
 
    # Minden telemetria-mintához megkeressük, melyik körbe tartozik
    tel = pd.merge_asof(tel, dl, left_on="SessionTime", right_on="LapStart",
                        direction="backward")
    tel = tel[tel["SessionTime"] <= tel["LapEnd"]].copy()
    if tel.empty:
        continue
 
    # Leggyorsabb teljes kör
    cnt = tel.groupby("LapNumber").size()
    full = cnt[cnt >= 0.8 * cnt.median()].index
    cand = tel[tel["LapNumber"].isin(full)].dropna(subset=["LapTimeSec"])
    if cand.empty:
        continue
    best = cand.loc[cand["LapTimeSec"].idxmin()]
    best_no = int(best["LapNumber"])
    lap = tel[tel["LapNumber"] == best_no].sort_values("SessionTime").copy()
 
    # Time: a kör elejétől eltelt idő. Distance: a sebességből integrált táv.
    t = (lap["SessionTime"] - lap["SessionTime"].iloc[0]).to_numpy(float)
    v = lap["Speed"].to_numpy(float) / 3.6   # km/h -> m/s
    lap["Time"] = t
    lap["Distance"] = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(t))])
    lap["Brake"] = lap["Brake"].fillna(0).astype(int)
 
    keep = [c for c in ["Time", "Distance", "Speed", "Throttle", "Brake", "nGear", "RPM", "DRS"]
            if c in lap.columns]
    lap[keep].to_csv(TEL_OUT / f"round_{rn:02d}_{abbr}.csv", index=False)
    tel_rows.append({"RoundNumber": rn, "Driver": abbr,
                     "LapTime": fmt_sec(float(best["LapTimeSec"])), "LapNumber": best_no})
 
# Index: melyik pilótához melyik kört mentettük el
pd.DataFrame(tel_rows).to_csv(TEL_INDEX, index=False)

 
# Időjárás segédfüggvények
 
# Timedelta
def fmt_td(td):
    if pd.isna(td):
        return None
    return fmt_sec(td.total_seconds())
 
# Átlagos felhőzet (%) a futam idején (Open-Meteo archív API-t használja)
def cloud_cover(lat, lon, date):
    import requests
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": lat, "longitude": lon, "start_date": date,
                    "end_date": date, "hourly": "cloud_cover", "timezone": "auto"},
            timeout=30,
        )
        r.raise_for_status()
        vals = r.json()["hourly"]["cloud_cover"][12:18]
        return sum(vals) / len(vals)
    except Exception as e:
        print("   felhőzet hiba:", e)
        return None
 
 
# Szöveges időjárás-címke az eső és a felhőzet alapján
def weather_label(rain_pct, clouds):
    if rain_pct and rain_pct > 0:
        return "Esős"
    if clouds is None:
        return None
    if clouds < 25:
        return "Napos"
    if clouds < 60:
        return "Részben felhős"
    return "Felhős"

 
# 9. Ellenőrzés: 
#TOP 5 pilóta:
#       FullName        TeamName  TotalPoints
# Max Verstappen Red Bull Racing        575.0
#   Sergio Perez Red Bull Racing        285.0
# Lewis Hamilton        Mercedes        234.0
#Fernando Alonso    Aston Martin        206.0
#Charles Leclerc         Ferrari        206.0
#
#TOP 5 csapat:
#       TeamName  TotalPoints
#Red Bull Racing        860.0
#       Mercedes        409.0
#        Ferrari        406.0
#        McLaren        302.0
#   Aston Martin        280.0
#
#Verstappen: {'races': 22, 'wins': 19, 'podiums': 21, 'poles': 12, 'fastest_laps': 9, 'laps_completed': 1325, 'points': 575.0}
#
#Telemetria fájlok: 67 | stintek: 208 | zászlós körök: 160
#
#Kész, a fájlok itt vannak: ...

print("\nTOP 5 pilóta:")
print(drivers.head(5)[["FullName", "TeamName", "TotalPoints"]].to_string(index=False))
print("\nTOP 5 csapat:")
print(teams.head(5)[["TeamName", "TotalPoints"]].to_string(index=False))
print("\nVerstappen:", stats)
print("\nTelemetria fájlok:", len(tel_rows), "| stintek:", len(stint_rows),
      "| zászlós körök:", len(flag_rows))
print("\nKész, a fájlok itt vannak:", OUT.resolve())
 
