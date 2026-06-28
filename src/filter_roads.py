# -*- coding: utf-8 -*-
"""Обрезка точек по реальным дорогам (OSM/Overpass): убираем придорожные точки,
оставляя замеры в поле/лесу, не на дорогах. Сохраняет геометрию дорог для карты.
"""
import os, csv, json, ssl, urllib.request, urllib.parse
import numpy as np
import config as C

CTX = ssl.create_default_context()
ROAD_BUFFER_M = 60.0   # минимальное удаление точки от дороги

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def fetch_roads():
    import time
    F = C.FIELD
    pad = 0.002
    s, w, n, e = F["lat_s"]-pad, F["lon_w"]-pad, F["lat_n"]+pad, F["lon_e"]+pad
    q = (f"[out:json][timeout:25];way[\"highway\"]({s},{w},{n},{e});out geom;")
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in OVERPASS_MIRRORS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "agrogeo/1.0"})
                with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
                    j = json.loads(r.read().decode("utf-8"))
                roads = []
                for el in j.get("elements", []):
                    geom = el.get("geometry")
                    if geom and len(geom) >= 2:
                        roads.append([(p["lon"], p["lat"]) for p in geom])
                print(f"  Overpass OK: {url.split('/')[2]} ({len(roads)} дорог)")
                return roads
            except Exception as ex:
                last = ex
                print(f"  {url.split('/')[2]} попытка {attempt+1}: {type(ex).__name__}")
                time.sleep(3)
    raise last


def to_m(lon, lat):
    return ((np.asarray(lon)-C.FIELD["lon_w"])*C.M_PER_DEG_LON,
            (np.asarray(lat)-C.FIELD["lat_s"])*C.M_PER_DEG_LAT)


def pt_seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx-ax, by-ay
    L2 = dx*dx+dy*dy
    if L2 == 0:
        return np.hypot(px-ax, py-ay)
    t = max(0.0, min(1.0, ((px-ax)*dx+(py-ay)*dy)/L2))
    return np.hypot(px-(ax+t*dx), py-(ay+t*dy))


def min_dist_to_roads(px, py, roads_m):
    best = 1e18
    for seg in roads_m:
        for i in range(len(seg)-1):
            ax, ay = seg[i]; bx, by = seg[i+1]
            d = pt_seg_dist(px, py, ax, ay, bx, by)
            if d < best:
                best = d
    return best


def main():
    raw = os.path.join(C.DATA_DIR, "raw_measurements.csv")
    rows = list(csv.DictReader(open(raw, encoding="utf-8")))
    try:
        roads = fetch_roads()
    except Exception as ex:
        print("Overpass недоступен:", ex, "— обрезка пропущена")
        return len(rows)
    # дороги в метрах
    roads_m = []
    for seg in roads:
        xs, ys = to_m([p[0] for p in seg], [p[1] for p in seg])
        roads_m.append(list(zip(xs, ys)))
    # сохранить дороги для карты
    with open(os.path.join(C.DATA_DIR, "roads.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": seg}}
            for seg in roads]}, f, ensure_ascii=False)

    kept = []
    for r in rows:
        px, py = to_m(float(r["lon"]), float(r["lat"]))
        d = min_dist_to_roads(float(px), float(py), roads_m)
        if d >= ROAD_BUFFER_M:
            kept.append(r)
    # перезаписать CSV только оставленными точками, перенумеровать
    fields = list(rows[0].keys())
    with open(raw, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(kept, 1):
            r["point_id"] = i
            w.writerow(r)
    print(f"OK filter_roads: дорог {len(roads)} сегм.; точек {len(rows)} -> {len(kept)} "
          f"(убрано {len(rows)-len(kept)} в радиусе {ROAD_BUFFER_M:.0f} м от дорог)")
    return len(kept)


if __name__ == "__main__":
    main()
