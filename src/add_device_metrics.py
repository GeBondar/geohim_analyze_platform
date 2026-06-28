# -*- coding: utf-8 -*-
"""Гибрид: добавляет к реальным данным SoilGrids слои, ИЗМЕРЯЕМЫЕ ПРИБОРОМ комплекса
(EC, температура, доступные P и K) — их нет в открытых данных. Значения синтезируются
правдоподобно и физически связанно с реальными свойствами почвы (помечены source=device).
"""
import os, csv
import numpy as np
import config as C


def main():
    raw = os.path.join(C.DATA_DIR, "raw_measurements.csv")
    rows = list(csv.DictReader(open(raw, encoding="utf-8")))
    rng = np.random.default_rng(C.SEED + 7)
    F = C.FIELD

    def col(k):
        return np.array([float(r[k]) for r in rows])
    vwc, n, soc, cec, clay = col("vwc"), col("n"), col("soc"), col("cec"), col("clay")
    lon = col("lon")
    nrm = lambda a: (a - a.mean())
    nx = (lon - F["lon_w"]) / (F["lon_e"] - F["lon_w"] + 1e-9)

    # EC ~ ЕКО, влажность, азот (ионная сила)
    ec = 0.12 + 0.011 * cec + 0.006 * vwc + 0.012 * n + rng.normal(0, 0.03, len(rows))
    # Температура почвы ~ пространственный градиент инсоляции
    t = 13.5 + 4.5 * nx + 0.04 * nrm(-soc) + rng.normal(0, 0.3, len(rows))
    # Доступный фосфор ~ азот, орг. вещество
    p = 9 + 0.9 * n + 0.05 * soc + rng.normal(0, 4.0, len(rows))
    # Доступный калий ~ ЕКО, глина
    k = 35 + 1.8 * cec + 1.3 * clay + rng.normal(0, 8.0, len(rows))

    ec = np.clip(ec, 0.05, 2.0); t = np.clip(t, 8, 26)
    p = np.clip(p, 5, 160); k = np.clip(k, 40, 320)

    dev = {"ec": ec, "t": t, "p": p, "k": k}
    fields = list(rows[0].keys())
    # вставляем device-колонки перед qc_flag
    insert_at = fields.index("qc_flag")
    for key in ["ec", "t", "p", "k"]:
        if key not in fields:
            fields.insert(insert_at, key); insert_at += 1

    for i, r in enumerate(rows):
        r["ec"] = round(float(dev["ec"][i]), 4)
        r["t"] = round(float(dev["t"][i]), 2)
        r["p"] = round(float(dev["p"][i]), 2)
        r["k"] = round(float(dev["k"][i]), 2)

    with open(raw, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"OK add_device_metrics: добавлены слои прибора EC,T,P,K к {len(rows)} точкам")
    return len(rows)


if __name__ == "__main__":
    main()
