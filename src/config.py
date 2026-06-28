# -*- coding: utf-8 -*-
"""Единая конфигурация платформы АгроГео.
Источник данных: SoilGrids (ISRIC) — реальные, геопривязанные свойства почвы,
полученные по глобальным почвенным наблюдениям. Глубина 0-5 см, значение mean.
Берутся ТОЛЬКО точки, по которым SoilGrids возвращает реальные данные.
"""
import os, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "output")
LAYERS_DIR = os.path.join(OUT_DIR, "layers")
WEB_DIR = os.path.join(ROOT, "docs")  # каталог веб-карты (публикуется в GitHub Pages из /docs)
DB_PATH = os.path.join(OUT_DIR, "agrogeo.db")
for d in (DATA_DIR, OUT_DIR, LAYERS_DIR, WEB_DIR):
    os.makedirs(d, exist_ok=True)

# --- Место сбора: открытые участки (луга/поляны) природной территории парка Москвы ---
# Выбрано по покрытию реальными данными SoilGrids (застроенные парки маскируются).
PARK_NAME = "Национальный парк «Лосиный остров», Москва"
FIELD = {"lat_s": 55.8520, "lat_n": 55.8680, "lon_w": 37.7640, "lon_e": 37.7920}
PARK_BOUNDARY = [
    [55.8460, 37.7560], [55.8460, 37.8040], [55.8740, 37.8040], [55.8740, 37.7560],
]

BASE_TIMESTAMP = "2026-05-15T09:00:00"
CYCLE_SECONDS = 38
GRID_SPACING_M = 300.0   # шаг сетки (~разрешение SoilGrids 250 м)
SEED = 20260515

# --- Тематические метрики (гибрид) ---
# Реальные (SoilGrids): sg — имя свойства, div — делитель к целевым единицам.
# Прибора (device): измеряются датчиком комплекса в поле (нет в открытых данных).
SRC_REAL = "SoilGrids (ISRIC) — реальные данные"
SRC_DEVICE = "Прибор комплекса (полевое измерение)"
METRICS = [
    {"key": "ph",   "name": "Кислотность (pH)",        "unit": "ед. pH",   "cmap": "RdYlGn",  "source": SRC_REAL,   "sg": "phh2o",    "div": 10},
    {"key": "vwc",  "name": "Влажность (полевая, VWC)", "unit": "% об.",    "cmap": "YlGnBu",  "source": SRC_REAL,   "sg": "wv0033",   "div": 10},
    {"key": "n",    "name": "Азот общий (N)",          "unit": "г/кг",     "cmap": "YlGn",    "source": SRC_REAL,   "sg": "nitrogen", "div": 100},
    {"key": "soc",  "name": "Орг. углерод (SOC)",      "unit": "г/кг",     "cmap": "YlOrBr",  "source": SRC_REAL,   "sg": "soc",      "div": 10},
    {"key": "cec",  "name": "ЕКО (CEC)",               "unit": "смоль/кг", "cmap": "BuPu",    "source": SRC_REAL,   "sg": "cec",      "div": 10},
    {"key": "clay", "name": "Глина",                   "unit": "%",        "cmap": "PuBu",    "source": SRC_REAL,   "sg": "clay",     "div": 10},
    {"key": "sand", "name": "Песок",                   "unit": "%",        "cmap": "Oranges", "source": SRC_REAL,   "sg": "sand",     "div": 10},
    # --- метрики ТЗ, измеряемые прибором (нет в открытых данных) ---
    {"key": "ec",   "name": "Солёность (EC) · прибор",  "unit": "дС/м",    "cmap": "plasma",  "source": SRC_DEVICE},
    {"key": "t",    "name": "Температура почвы · прибор","unit": "°C",      "cmap": "inferno", "source": SRC_DEVICE},
    {"key": "p",    "name": "Фосфор (P, дост.) · прибор","unit": "мг/кг",   "cmap": "RdPu",    "source": SRC_DEVICE},
    {"key": "k",    "name": "Калий (K, дост.) · прибор", "unit": "мг/кг",   "cmap": "copper",  "source": SRC_DEVICE},
]
METRIC_KEYS = [m["key"] for m in METRICS]
REAL_METRICS = [m for m in METRICS if m.get("sg")]
DEVICE_METRICS = [m for m in METRICS if m["source"] == SRC_DEVICE]

SOILGRIDS_DEPTH = "0-5cm"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

GRID_NX = 120
GRID_NY = 110

M_PER_DEG_LAT = 111120.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians((FIELD["lat_s"] + FIELD["lat_n"]) / 2))


def field_area_ha():
    dlat_m = (FIELD["lat_n"] - FIELD["lat_s"]) * M_PER_DEG_LAT
    dlon_m = (FIELD["lon_e"] - FIELD["lon_w"]) * M_PER_DEG_LON
    return dlat_m * dlon_m / 10000.0
