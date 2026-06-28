# -*- coding: utf-8 -*-
"""КП Этап 2, работа 1 (источник данных): получение РЕАЛЬНЫХ свойств почвы
из SoilGrids (ISRIC) по сетке точек в открытом поле парка Москвы.
Берутся ТОЛЬКО точки, по которым есть реальные данные (остальные пропускаются).
"""
import os, csv, json, time, ssl, urllib.request, urllib.error
from datetime import datetime, timedelta
import numpy as np
import config as C

CTX = ssl.create_default_context()
SLEEP = 7.0          # пауза между запросами (лимиты API)
RETRIES = 4


def query_point(lon, lat):
    props = "".join(f"&property={m['sg']}" for m in C.REAL_METRICS)
    url = (f"{C.SOILGRIDS_URL}?lon={lon:.5f}&lat={lat:.5f}{props}"
           f"&depth={C.SOILGRIDS_DEPTH}&value=mean")
    req = urllib.request.Request(url, headers={"User-Agent": "agrogeo-platform/1.0"})
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    raw = {}
    for layer in data["properties"]["layers"]:
        raw[layer["name"]] = layer["depths"][0]["values"].get("mean")
    vals = {}
    for m in C.REAL_METRICS:
        v = raw.get(m["sg"])
        vals[m["key"]] = None if v is None else round(v / m["div"], 3)
    return vals


def grid_points():
    F = C.FIELD
    dlat_m = (F["lat_n"] - F["lat_s"]) * C.M_PER_DEG_LAT
    dlon_m = (F["lon_e"] - F["lon_w"]) * C.M_PER_DEG_LON
    nr = max(3, int(round(dlat_m / C.GRID_SPACING_M)) + 1)
    nc = max(3, int(round(dlon_m / C.GRID_SPACING_M)) + 1)
    lats = np.linspace(F["lat_s"], F["lat_n"], nr)
    lons = np.linspace(F["lon_w"], F["lon_e"], nc)
    pts = []
    for i, la in enumerate(lats):
        row = list(lons) if i % 2 == 0 else list(lons[::-1])
        for lo in row:
            pts.append((float(la), float(lo)))
    return pts


def main():
    pts = grid_points()
    raw_csv = os.path.join(C.DATA_DIR, "raw_measurements.csv")
    t0 = datetime.fromisoformat(C.BASE_TIMESTAMP)
    valid = 0; total = len(pts); pid = 0
    with open(raw_csv, "w", newline="", encoding="utf-8") as f:
        real_keys = [m["key"] for m in C.REAL_METRICS]
        w = csv.writer(f)
        w.writerow(["point_id", "ts", "lon", "lat"] + real_keys + ["qc_flag", "calib_level", "source"])
        for idx, (la, lo) in enumerate(pts):
            vals = None
            for attempt in range(RETRIES):
                try:
                    vals = query_point(lo, la)
                    break
                except Exception as e:
                    print(f"  retry {attempt+1} @({la:.4f},{lo:.4f}): {type(e).__name__}")
                    time.sleep(SLEEP * (attempt + 2))
            if not vals or vals.get("ph") is None:
                print(f"  нет данных @({la:.5f},{lo:.5f}) — пропуск")
                time.sleep(SLEEP); continue
            pid += 1; valid += 1
            ts = (t0 + timedelta(seconds=pid * C.CYCLE_SECONDS)).isoformat()
            row = [pid, ts, round(lo, 6), round(la, 6)] + [vals[k] for k in real_keys] + [1, 3, "SoilGrids/ISRIC"]
            w.writerow(row); f.flush()
            print(f"  [{idx+1}/{total}] ok pid={pid}: pH={vals['ph']} N={vals['n']} VWC={vals['vwc']} SOC={vals['soc']}")
            time.sleep(SLEEP)

    # геометрия
    F = C.FIELD
    with open(os.path.join(C.DATA_DIR, "field.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "Feature", "properties": {"name": "Участок обследования", "area_ha": round(C.field_area_ha(), 2)},
                   "geometry": {"type": "Polygon", "coordinates": [[
                       [F["lon_w"], F["lat_s"]], [F["lon_e"], F["lat_s"]],
                       [F["lon_e"], F["lat_n"]], [F["lon_w"], F["lat_n"]], [F["lon_w"], F["lat_s"]]]]}},
                  f, ensure_ascii=False)
    with open(os.path.join(C.DATA_DIR, "park.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "Feature", "properties": {"name": C.PARK_NAME},
                   "geometry": {"type": "Polygon", "coordinates": [[[lo, la] for la, lo in C.PARK_BOUNDARY] + [[C.PARK_BOUNDARY[0][1], C.PARK_BOUNDARY[0][0]]]]}},
                  f, ensure_ascii=False)

    print(f"OK fetch_real_data: {valid}/{total} точек с реальными данными SoilGrids -> {raw_csv}")
    return valid


if __name__ == "__main__":
    main()
