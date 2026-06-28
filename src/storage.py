# -*- coding: utf-8 -*-
"""КП Этап 2, работа 1: система хранения геохимических данных (демо-реализация).
В продакшене — PostgreSQL/PostGIS/TimescaleDB (db/schema_postgres.sql).
В автономной демо-сборке — встроенный SQLite. Состав метрик берётся из config.METRICS.
"""
import os, sqlite3, csv
import pandas as pd
import config as C

METRIC_COLS = ", ".join(f"{k} REAL" for k in C.METRIC_KEYS)
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id INTEGER PRIMARY KEY,
    contract_no TEXT, field_name TEXT, started_at TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS measurements (
    measurement_id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    ts TEXT NOT NULL,
    lon REAL NOT NULL, lat REAL NOT NULL,
    {METRIC_COLS},
    qc_flag INTEGER DEFAULT 1, calib_level INTEGER DEFAULT 3, source TEXT
);
CREATE INDEX IF NOT EXISTS idx_meas_ts ON measurements(ts);
CREATE INDEX IF NOT EXISTS idx_meas_xy ON measurements(lon, lat);
"""


def build(csv_path=None):
    csv_path = csv_path or os.path.join(C.DATA_DIR, "raw_measurements.csv")
    if os.path.exists(C.DB_PATH):
        os.remove(C.DB_PATH)
    con = sqlite3.connect(C.DB_PATH)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO campaigns(campaign_id,contract_no,field_name,started_at,note) VALUES (?,?,?,?,?)",
                (1, "17098ГУ/2021", C.PARK_NAME, C.BASE_TIMESTAMP, "Обследование участка роботизированным комплексом"))
    cols = ["measurement_id", "campaign_id", "ts", "lon", "lat"] + C.METRIC_KEYS + ["qc_flag", "calib_level", "source"]
    placeholders = ",".join("?" * len(cols))
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            row = [int(r["point_id"]), 1, r["ts"], float(r["lon"]), float(r["lat"])]
            row += [float(r[k]) for k in C.METRIC_KEYS]
            row += [int(r["qc_flag"]), int(r["calib_level"]), r.get("source", "")]
            rows.append(row)
    con.executemany(f"INSERT INTO measurements({','.join(cols)}) VALUES ({placeholders})", rows)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    size_kb = os.path.getsize(C.DB_PATH) / 1024
    con.close()
    print(f"OK storage: SQLite {C.DB_PATH} — {n} записей, {size_kb:.0f} КБ")
    return C.DB_PATH


def load_measurements():
    con = sqlite3.connect(C.DB_PATH)
    df = pd.read_sql_query("SELECT * FROM measurements ORDER BY measurement_id", con)
    con.close()
    return df


if __name__ == "__main__":
    build()
