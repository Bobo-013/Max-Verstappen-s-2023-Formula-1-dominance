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

RES_COLS = ["Abbreviation", "FullName", "TeamName", "TeamColor", "Position",
            "GridPosition", "Points", "RoundNumber"]
sprint[RES_COLS].to_csv(OUT / "sprint_results.csv", index=False)
race[RES_COLS].to_csv(OUT / "race_results.csv", index=False)

# Időmérő a Results.csv Q1/Q2/Q3 oszlopaiból
def q_sec(v):
    if pd.isna(v):
        return np.nan
    s = str(v).strip()
    if s.lower() in ("", "nan", "nat", "none"):
        return np.nan
    try:
        if "days" in s:
            return pd.to_timedelta(s).total_seconds()
        p = s.split(":")
        if len(p) == 2:                      # "1:30.123"
            return int(p[0]) * 60 + float(p[1])
        return pd.to_timedelta(s).total_seconds()
    except Exception:
        return np.nan

q = pd.read_csv(DATA / "Results.csv",
                usecols=lambda c: c in set(RES_COLS + ["Q1", "Q2", "Q3"]),
                dtype={"TeamColor": str})
for k in ("Q1", "Q2", "Q3"):
    if k not in q.columns:
        q[k] = np.nan
    q[k + "Sec"] = q[k].map(q_sec)

# legjobb idő = a legutolsó szakasz ideje, amiben szerepelt
q["BestStage"] = np.select([q["Q3Sec"].notna(), q["Q2Sec"].notna(), q["Q1Sec"].notna()],
                           ["Q3", "Q2", "Q1"], default="")
q["BestSec"] = q["Q3Sec"].fillna(q["Q2Sec"]).fillna(q["Q1Sec"])
q["StageNo"] = q["BestStage"].map({"Q3": 3, "Q2": 2, "Q1": 1}).fillna(0)

# időmérős helyezés: Q3 → Q2 → Q1 kiesők, szakaszon belül idő szerint
q = q.sort_values(["RoundNumber", "StageNo", "BestSec"],
                  ascending=[True, False, True])
q["Position"] = q.groupby("RoundNumber").cumcount() + 1
q.loc[q["BestSec"].isna(), "Position"] = np.nan
q["GridPosition"] = q["Position"]
q["Points"] = 0

q["Best"] = q["BestSec"].map(lambda s: fmt_sec(s) if pd.notna(s) else "")
for k in ("Q1", "Q2", "Q3"):
    q[k] = q[k + "Sec"].map(lambda s: fmt_sec(s) if pd.notna(s) else "")

q_cols = RES_COLS + ["Best", "BestSec", "BestStage", "Q1", "Q2", "Q3"]
q = q[q["BestSec"].notna()]
q[q_cols].to_csv(OUT / "quali_results.csv", index=False)
print("Időmérő sorok:", len(q))

 
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

    # A futam leggyorsabb körét futó pilóta
    valid = laps_all[(laps_all["RoundNumber"] == rn)].dropna(subset=["LapTimeSec"])
    fastest = [valid.loc[valid["LapTimeSec"].idxmin(), "Driver"]] if not valid.empty else []

    return set(top3) | {"VER"} | set(fastest)
 
 
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

#Sprint időjárás
def weather_archive(lat, lon, date):
    import requests
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": lat, "longitude": lon, "start_date": date, "end_date": date,
                    "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,"
                              "wind_speed_10m,precipitation",
                    "wind_speed_unit": "ms", "timezone": "auto"},
            timeout=30)
        r.raise_for_status()
        h = r.json()["hourly"]

        def avg(k):
            vals = [v for v in h[k][12:18] if v is not None]
            return sum(vals) / len(vals) if vals else None

        rain = [v for v in h["precipitation"][12:18] if v is not None]
        return {"air_temp": avg("temperature_2m"), "humidity": avg("relative_humidity_2m"),
                "pressure": avg("surface_pressure"), "wind_speed": avg("wind_speed_10m"),
                "rain_pct": 100 * sum(v > 0 for v in rain) / len(rain) if rain else None}
    except Exception as e:
        print("   időjárás hiba:", e)
        return {}
 
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

#9. Szezon összefoglaló
WITHIN= 1.15

CLOUD_CACHE = OUT / "cloud_cover_cache.csv"
cloud = (pd.read_csv(CLOUD_CACHE, index_col=0)["CloudCover"].to_dict()
         if CLOUD_CACHE.exists()
         else{})

weather = pd.read_csv(DATA / "Weather.csv")

WEATHER_COLS = [("air_temp", "AirTemp"), ("track_temp", "TrackTemp"), ("pressure", "Pressure"), ("humidity", "Humidity"), ("wind_speed", "WindSpeed")]
summary_rows = []
for rn in rounds:
    rn = int(rn)
    row = {"RoundNumber" : rn}
    lr = laps_all[laps_all["RoundNumber"] == rn] 
    valid = lr.dropna(subset = ["LapTimeSec"])
    
    #Köridők
    if not valid.empty:
        fast = valid.loc[valid["LapTimeSec"].idxmin()]
        ok = valid[valid["LapTimeSec"] <= fast["LapTimeSec"] * WITHIN]
        ver_all = valid[valid["Driver"] == "VER"]
        ver_ok = ok[ok["Driver"] == "VER"]
        row["ver_best"] = fmt_sec(ver_all["LapTimeSec"].min()) if not ver_all.empty else None
        row["ver_avg"] = fmt_sec(ver_ok["LapTimeSec"].mean()) if not ver_ok.empty else None
        row["avg_all"] = fmt_sec(ok["LapTimeSec"].mean())
        row["fastest_driver"] = fast["Driver"]
        row["fastest_lap_no"] = int(fast["LapNumber"])
        row["fastest_time"] = fmt_sec(fast["LapTimeSec"])
        
    #Időjárás szűrés
    w = (weather[weather["RoundNumber"] == rn]
        if "RoundNumber" in weather.columns 
        else weather.iloc[0:0])
    
    if not w.empty and "Time" in w.columns and not lr.empty:
        t = pd.to_timedelta(w["Time"], errors="coerce").dt.total_seconds()
        inside = w[(t >= lr["LapStart"].min()) & (t <= lr["LapEnd"].max())]
        if not inside.empty:
            w = inside
    
    for out_col, scr_col in WEATHER_COLS:
        if not w.empty and scr_col in w.columns:
            row[out_col] = pd.to_numeric(w[scr_col], errors="coerce").mean()
    
    if not w.empty and "Rainfall" in w.columns:
        rain = w["Rainfall"].astype(str).str.lower().isin(["true", "1", "1.0"])
        row["rain_pct"] = rain.mean() * 100
    
# Felhőzet
    ev = events[events["RoundNumber"] == rn].iloc[0]
    if pd.isna(cloud.get(rn)) and pd.notna(ev["Lat"]):
        c = cloud_cover(ev["Lat"], ev["Lon"], str(ev["EventDate"])[:10])
        cloud[rn] = np.nan if c is None else c

    clouds = cloud.get(rn)
    clouds = None if pd.isna(clouds) else float(clouds)

    row["cloud_cover"] = clouds
    row["condition"] = weather_label(row.get("rain_pct"), clouds)

    summary_rows.append(row)

pd.Series(cloud, name = "CloudCover").to_csv(CLOUD_CACHE, index_label="RoundNumber")
summary_cols = ["RoundNumber", "ver_best", "ver_avg", "avg_all", "fastest_driver", "fastest_lap_no", "fastest_time", 
                "condition", "cloud_cover", "air_temp", "track_temp", "pressure", "humidity", "wind_speed", "rain_pct"]

pd.DataFrame(summary_rows).reindex(columns=summary_cols).to_csv(OUT / "race_summary.csv", index=False)

#10. Sprint
#Egy sprint időjárását a Time oszlopból határozza meg
def sprint_weather(wr, lr):
    if wr.empty or lr.empty:
        return wr.iloc[0:0]
    wr = wr.assign(_t=pd.to_timedelta(wr["Time"], errors="coerce").dt.total_seconds())
    wr = wr.dropna(subset=["_t"])
    seg = (wr["_t"].diff() < 0).cumsum()
    if seg.nunique() < 2:
        return wr.iloc[0:0]
    end = lr["LapEnd"].max()
    return min(wr.groupby(seg), key=lambda kv: abs(kv[1]["_t"].max() - end))[1]


sp_rounds = sorted(int(r) for r in sprint["RoundNumber"].dropna().unique())
SPRINT_LAPS = DATA / "Sprint_Laps.csv"
SP_CACHE = OUT / "sprint_cloud_cache.csv"
sp_weather_n = 0

if sp_rounds:
    # Sprint köridők: ha nincs Sprint_Laps.csv, üres táblával megyünk tovább (csak időjárás készül)
    if SPRINT_LAPS.exists():
        sl = pd.read_csv(SPRINT_LAPS, usecols=lambda c: c in set(LAP_COLS))
        sl = sl.dropna(subset=["RoundNumber", "DriverNumber", "LapNumber"]).copy()
        for c in ["RoundNumber", "DriverNumber", "LapNumber"]:
            sl[c] = sl[c].astype(int)
        sl["LapStart"] = pd.to_timedelta(sl["LapStartTime"]).dt.total_seconds()
        sl["LapEnd"] = pd.to_timedelta(sl["Time"]).dt.total_seconds()
        sl["LapTimeSec"] = pd.to_timedelta(sl["LapTime"]).dt.total_seconds()
    else:
        print("Sprint_Laps.csv hiányzik: a sprint köridők kimaradnak, csak az időjárás készül el")
        sl = pd.DataFrame(columns=LAP_COLS + ["LapStart", "LapEnd", "LapTimeSec"])

    sp_cloud = (pd.read_csv(SP_CACHE, index_col=0)["CloudCover"].to_dict()
                if SP_CACHE.exists() else {})
    best_rows, sum_rows = [], []

    for rn in sp_rounds:
        row = {"RoundNumber": rn}
        lr = sl[sl["RoundNumber"] == rn]
        valid = lr.dropna(subset=["LapTimeSec"])

        # Köridők
        if not valid.empty:
            top3 = (sprint[sprint["RoundNumber"] == rn].sort_values("Position")
                    .head(3)["Abbreviation"].tolist())
            fast = valid.loc[valid["LapTimeSec"].idxmin()]
            # A kiválasztott pilóták legjobb köre (telemetria helyett)
            for d in set(top3) | {"VER", fast["Driver"]}:
                dv = valid[valid["Driver"] == d]
                if dv.empty:
                    continue
                b = dv.loc[dv["LapTimeSec"].idxmin()]
                best_rows.append({"RoundNumber": rn, "Driver": d,
                                  "LapTime": fmt_sec(b["LapTimeSec"]),
                                  "LapNumber": int(b["LapNumber"])})
            ok = valid[valid["LapTimeSec"] <= fast["LapTimeSec"] * WITHIN]
            ver_all = valid[valid["Driver"] == "VER"]
            ver_ok = ok[ok["Driver"] == "VER"]
            row["ver_best"] = fmt_sec(ver_all["LapTimeSec"].min()) if not ver_all.empty else None
            row["ver_avg"] = fmt_sec(ver_ok["LapTimeSec"].mean()) if not ver_ok.empty else None
            row["avg_all"] = fmt_sec(ok["LapTimeSec"].mean())
            row["fastest_driver"] = fast["Driver"]
            row["fastest_lap_no"] = int(fast["LapNumber"])
            row["fastest_time"] = fmt_sec(fast["LapTimeSec"])

        # Időjárás a Weather.csv-ből: csak ha a sprint szegmense azonosítható
        if "RoundNumber" in weather.columns:
            w = sprint_weather(weather[weather["RoundNumber"] == rn], lr)
        else:
            w = weather.iloc[0:0]
        if not w.empty and not lr.empty:
            tt = pd.to_timedelta(w["Time"], errors="coerce").dt.total_seconds()
            inside = w[(tt >= lr["LapStart"].min()) & (tt <= lr["LapEnd"].max())]
            if not inside.empty:
                w = inside
        if not w.empty:
            sp_weather_n += 1
        for out_col, src in WEATHER_COLS:
            if not w.empty and src in w.columns:
                row[out_col] = pd.to_numeric(w[src], errors="coerce").mean()
        if not w.empty and "Rainfall" in w.columns:
            row["rain_pct"] = w["Rainfall"].astype(str).str.lower().isin(["true", "1", "1.0"]).mean() * 100

        # Ha nincs helyi időjárás, az archív API-ból pótoljuk (a sprint szombaton van: EventDate - 1 nap)
        ev = events[events["RoundNumber"] == rn].iloc[0]
        day = None
        if pd.notna(ev["Lat"]):
            day = (pd.to_datetime(str(ev["EventDate"])[:10]) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if pd.isna(row.get("air_temp")) and day:
            row.update(weather_archive(ev["Lat"], ev["Lon"], day))

        # Felhőzet
        if pd.isna(sp_cloud.get(rn)) and day:
            c = cloud_cover(ev["Lat"], ev["Lon"], day)
            sp_cloud[rn] = np.nan if c is None else c
        clouds = sp_cloud.get(rn)
        clouds = None if pd.isna(clouds) else float(clouds)

        row["cloud_cover"] = clouds
        row["condition"] = weather_label(row.get("rain_pct"), clouds)
        sum_rows.append(row)

    pd.Series(sp_cloud, name="CloudCover").to_csv(SP_CACHE, index_label="RoundNumber")
    pd.DataFrame(sum_rows).reindex(columns=summary_cols).to_csv(OUT / "sprint_summary.csv", index=False)
    pd.DataFrame(best_rows, columns=["RoundNumber", "Driver", "LapTime", "LapNumber"]).to_csv(
        OUT / "sprint_best_laps.csv", index=False)
    print(f"Sprint: {len(sp_rounds)} forduló | köridős sorok: {len(best_rows)} | "
          f"Weather.csv-ből azonosított időjárás: {sp_weather_n} forduló")
else:
    print("Nincs sprint forduló, a sprint rész kimarad")

#11. Időmérő eredmények
# A pilótát a rajtszám alapján párosítjuk a Results.csv-hez.
def q_sec(v):
    if pd.isna(v):
        return np.nan
    s = str(v).strip()
    if s.lower() in ("", "nan", "nat", "none", "\\n"):
        return np.nan
    try:
        if "days" in s:
            return pd.to_timedelta(s).total_seconds()
        p = s.split(":")
        if len(p) == 2:                      # "1:30.123"
            return int(p[0]) * 60 + float(p[1])
        return float(s)
    except Exception:
        return np.nan


Q_SRC = DATA / "qualifying.csv"
res_hdr = pd.read_csv(DATA / "Results.csv", nrows=0).columns
if not Q_SRC.exists() or not (DATA / "races_2023.csv").exists():
    print("FIGYELEM: nincs data/qualifying.csv vagy data/races_2023.csv, az időmérő kimarad")
elif "DriverNumber" not in res_hdr:
    print("FIGYELEM: a Results.csv-ben nincs DriverNumber oszlop, az időmérő kimarad.",
          "Oszlopok:", list(res_hdr))
else:
    q = pd.read_csv(Q_SRC, na_values=["\\N"])

    # raceId -> forduló: a letöltő script által mentett races_2023.csv alapján
    # (a lyukas raceId-ket, pl. a törölt imolai futamot is helyesen kezeli)
    rc = pd.read_csv(DATA / "races_2023.csv")
    q = q.merge(rc[["raceId", "round"]], on="raceId").rename(columns={"round": "RoundNumber"})
    print("Időmérő: futamok száma", q["raceId"].nunique(), "(22 kell)")
    q = q.rename(columns={"number": "DriverNumber", "position": "Position",
                          "q1": "Q1", "q2": "Q2", "q3": "Q3"})

    # név, csapat, szín a Results.csv-ből
    names = pd.read_csv(DATA / "Results.csv",
                        usecols=["RoundNumber", "DriverNumber", "Abbreviation",
                                 "FullName", "TeamName", "TeamColor"],
                        dtype={"TeamColor": str})
    for d in (q, names):
        d["DriverNumber"] = pd.to_numeric(d["DriverNumber"], errors="coerce").astype("Int64")
    names = names.drop_duplicates(["RoundNumber", "DriverNumber"])
    q = q.merge(names, on=["RoundNumber", "DriverNumber"], how="left")
    print("Időmérő: nem párosított pilóta:", int(q["FullName"].isna().sum()))
    q = q.dropna(subset=["Abbreviation"]).copy()

    for k in ("Q1", "Q2", "Q3"):
        q[k + "Sec"] = q[k].map(q_sec)

    # legjobb idő = a legutolsó szakasz ideje, amiben szerepelt
    q["BestStage"] = np.select([q["Q3Sec"].notna(), q["Q2Sec"].notna(), q["Q1Sec"].notna()],
                               ["Q3", "Q2", "Q1"], default="")
    q["BestSec"] = q["Q3Sec"].fillna(q["Q2Sec"]).fillna(q["Q1Sec"])
    q["Position"] = pd.to_numeric(q["Position"], errors="coerce")
    q["GridPosition"] = q["Position"]
    q["Points"] = 0

    q["Best"] = q["BestSec"].map(lambda s: fmt_sec(s) if pd.notna(s) else "")
    for k in ("Q1", "Q2", "Q3"):
        q[k] = q[k + "Sec"].map(lambda s: fmt_sec(s) if pd.notna(s) else "")

    q_cols = RES_COLS + ["Best", "BestSec", "BestStage", "Q1", "Q2", "Q3"]
    q = q[q["BestSec"].notna()]
    q[q_cols].to_csv(OUT / "quali_results.csv", index=False)
    print("Időmérő sorok:", len(q))
    poles = q[q["Position"] == 1].sort_values("RoundNumber")
    print("Pole-sitterek (1. forduló VER, 21. LEC, 22. VER kell):",
          dict(zip(poles["RoundNumber"], poles["Abbreviation"])))

 
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

# 12. Ellenőrzés: 
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
 
