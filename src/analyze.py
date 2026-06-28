# -*- coding: utf-8 -*-
"""КП Этап 2, работы 2 и 5: анализ больших геохимических данных и выявление корреляций.
Конвейер: очистка/QC -> калибровка -> пространственная интерполяция (IDW и ординарный
кригинг) с перекрёстной проверкой -> 7 тематических слоёв -> корреляции/PCA/Moran's I.
Результаты выгружаются для веб-визуализации (web/layers_data.js) и в авто-отчёт.
"""
import os, io, json, base64, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial.distance import cdist
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

import config as C
import storage

EPS = 1e-9


# ---------- геокоординаты -> локальные метры ----------
def to_meters(lon, lat):
    x = (np.asarray(lon) - C.FIELD["lon_w"]) * C.M_PER_DEG_LON
    y = (np.asarray(lat) - C.FIELD["lat_s"]) * C.M_PER_DEG_LAT
    return np.column_stack([x, y])


# ---------- очистка / контроль качества ----------
def clean(df):
    n0 = len(df)
    d = df[df["qc_flag"] == 1].copy()
    # робастная фильтрация выбросов (модифицированный z-показатель по медиане/MAD)
    mask = np.ones(len(d), dtype=bool)
    for k in C.METRIC_KEYS:
        x = d[k].to_numpy()
        med = np.median(x); mad = np.median(np.abs(x - med))
        if mad <= 1e-9:            # нет разброса по метрике — фильтр неприменим
            continue
        z = 0.6745 * (x - med) / mad
        mask &= np.abs(z) < 5.0    # отбраковываем только грубые выбросы
    d = d[mask].copy()
    valid_frac = len(d) / n0
    return d, valid_frac


# ---------- калибровка ----------
def calibrate(df):
    # Данные SoilGrids уже приведены к целевым единицам — синтетическая поправка
    # не применяется (значения используются как есть). Шаг оставлен как точка
    # расширения для калибровки сырого сигнала прибора в продакшене.
    return df.copy()


# ---------- вариограмма / кригинг ----------
def _gamma(h, nugget, psill, rng):
    return nugget + psill * (1.0 - np.exp(-3.0 * h / (rng + EPS)))


def krige_grid(S, z, G):
    """Ординарный кригинг (экспоненциальная вариограмма). S(n,2) z(n) G(g,2) метры."""
    n = len(S)
    sill = np.var(z) + EPS
    nugget = 0.05 * sill
    psill = sill - nugget
    diag = math.hypot(*(S.max(0) - S.min(0)))
    rng = 0.45 * diag
    Dss = cdist(S, S)
    A = np.ones((n + 1, n + 1)); A[:n, :n] = _gamma(Dss, nugget, psill, rng); A[n, n] = 0.0
    Ainv = np.linalg.pinv(A)
    Dgs = cdist(G, S)
    RHS = np.ones((n + 1, len(G))); RHS[:n, :] = _gamma(Dgs, nugget, psill, rng).T
    W = Ainv @ RHS
    est = z @ W[:n, :]
    return est


def idw_grid(S, z, G, power=2.0):
    D = cdist(G, S) + EPS
    Wt = 1.0 / D ** power
    return (Wt * z).sum(1) / Wt.sum(1)


def loo_rmse(S, z, method):
    """Перекрёстная проверка (leave-one-out) RMSE."""
    n = len(S)
    if method == "idw":
        D = cdist(S, S); np.fill_diagonal(D, np.inf); D += EPS
        Wt = 1.0 / D ** 2
        pred = (Wt * z).sum(1) / Wt.sum(1)
    else:  # kriging
        pred = np.empty(n)
        for i in range(n):
            idx = np.arange(n) != i
            pred[i] = krige_grid(S[idx], z[idx], S[i:i+1])[0]
    return float(np.sqrt(np.mean((pred - z) ** 2)))


# ---------- слой -> PNG (base64) ----------
def grid_to_png_b64(grid, cmap, vmin, vmax, png_path):
    buf = io.BytesIO()
    plt.imsave(buf, grid, cmap=cmap, vmin=vmin, vmax=vmax, format="png", origin="upper")
    data = buf.getvalue()
    with open(png_path, "wb") as f:
        f.write(data)
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def colorbar_b64(cmap, w=240, h=18):
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    buf = io.BytesIO()
    plt.imsave(buf, np.repeat(grad, 12, axis=0), cmap=cmap, format="png")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ---------- корреляции / PCA / Moran's I ----------
def morans_i(S, x, thresh=None):
    n = len(S)
    D = cdist(S, S)
    if thresh is None:
        thresh = 2.2 * C.GRID_SPACING_M
    with np.errstate(divide="ignore"):
        inv = np.where(D > 0, 1.0 / D, 0.0)
    Wt = np.where((D > 0) & (D <= thresh), inv, 0.0)
    rs = Wt.sum(1, keepdims=True); rs[rs == 0] = 1
    Wt = Wt / rs
    z = x - x.mean()
    S0 = Wt.sum()
    num = (Wt * np.outer(z, z)).sum()
    den = (z * z).sum() + EPS
    return float((n / S0) * (num / den))


def main():
    df = storage.load_measurements()
    n_raw = len(df)
    clean_df, valid_frac = clean(df)
    cal_df = calibrate(clean_df)

    S = to_meters(cal_df["lon"], cal_df["lat"])

    # сетка интерполяции (row0 = север)
    gx = np.linspace(C.FIELD["lon_w"], C.FIELD["lon_e"], C.GRID_NX)
    gy = np.linspace(C.FIELD["lat_n"], C.FIELD["lat_s"], C.GRID_NY)
    GX, GY = np.meshgrid(gx, gy)
    G = to_meters(GX.ravel(), GY.ravel())
    bounds = [[C.FIELD["lat_s"], C.FIELD["lon_w"]], [C.FIELD["lat_n"], C.FIELD["lon_e"]]]

    layers = []
    accuracy = {}
    for m in C.METRICS:
        k = m["key"]
        z = cal_df[k].to_numpy()
        grid = krige_grid(S, z, G).reshape(C.GRID_NY, C.GRID_NX)
        vmin, vmax = float(np.nanmin(grid)), float(np.nanmax(grid))
        if vmax - vmin < 1e-9:     # плоский слой (метрика однородна) — чтобы PNG отрисовался
            vmax = vmin + 1e-6
        png_path = os.path.join(C.LAYERS_DIR, f"{k}.png")
        b64 = grid_to_png_b64(grid, m["cmap"], vmin, vmax, png_path)
        rmse_idw = loo_rmse(S, z, "idw")
        rmse_kr = loo_rmse(S, z, "kriging")
        rel = 100.0 * rmse_kr / (abs(z.mean()) + EPS)
        accuracy[k] = {"rmse_idw": round(rmse_idw, 4), "rmse_kriging": round(rmse_kr, 4),
                       "rel_pct": round(rel, 2)}
        layers.append({
            "key": k, "name": m["name"], "unit": m["unit"], "cmap": m["cmap"],
            "source": m["source"], "device": m["source"] == C.SRC_DEVICE,
            "min": round(vmin, 3), "max": round(vmax, 3),
            "mean": round(float(z.mean()), 3), "png": b64, "bounds": bounds,
            "colorbar": colorbar_b64(m["cmap"]),
            "rmse_kriging": round(rmse_kr, 4), "rel_pct": round(rel, 2),
        })
        print(f"  слой {k}: min={vmin:.2f} max={vmax:.2f} LOO-RMSE idw={rmse_idw:.3f} krig={rmse_kr:.3f} ({rel:.1f}%)")

    # точки (GeoJSON) для просмотра значений
    feats = []
    for _, r in cal_df.iterrows():
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [round(r["lon"], 7), round(r["lat"], 7)]},
                      "properties": {k: round(float(r[k]), 2) for k in C.METRIC_KEYS} | {"id": int(r["measurement_id"]), "ts": r["ts"]}})
    points_geojson = {"type": "FeatureCollection", "features": feats}

    # корреляции
    M = cal_df[C.METRIC_KEYS]
    pearson = M.corr(method="pearson").round(3)
    spearman = M.corr(method="spearman").round(3)

    # PCA
    Xs = StandardScaler().fit_transform(M.to_numpy())
    pca = PCA().fit(Xs)
    evr = pca.explained_variance_ratio_

    # Moran's I по азоту
    mi_n = morans_i(S, cal_df["n"].to_numpy())

    # топ значимых пар корреляций
    pairs = []
    keys = C.METRIC_KEYS
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            pairs.append((keys[i], keys[j], float(pearson.iloc[i, j])))
    pairs.sort(key=lambda t: -abs(t[2]))

    # матрица корреляций -> PNG
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    im = ax.imshow(pearson.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(keys))); ax.set_yticks(range(len(keys)))
    ax.set_xticklabels([x.upper() for x in keys]); ax.set_yticklabels([x.upper() for x in keys])
    for i in range(len(keys)):
        for j in range(len(keys)):
            ax.text(j, i, f"{pearson.iloc[i,j]:.2f}", ha="center", va="center",
                    color="white" if abs(pearson.iloc[i, j]) > 0.5 else "black", fontsize=8)
    ax.set_title("Корреляции метрик (Пирсон)")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout()
    corr_png = os.path.join(C.OUT_DIR, "correlations.png")
    fig.savefig(corr_png, dpi=120); plt.close(fig)
    with open(corr_png, "rb") as f:
        corr_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")

    correlations = {
        "pearson": pearson.to_dict(),
        "spearman": spearman.to_dict(),
        "top_pairs": [{"a": a, "b": b, "r": round(r, 3)} for a, b, r in pairs[:6]],
        "pca_evr": [round(float(v), 4) for v in evr],
        "pca_first2": round(float(evr[0] + evr[1]), 4),
        "morans_I_n": round(mi_n, 3),
        "image": corr_b64,
    }

    meta = {
        "park": C.PARK_NAME, "contract": "17098ГУ/2021",
        "field_area_ha": round(C.field_area_ha(), 2),
        "n_raw": n_raw, "n_clean": len(cal_df),
        "valid_frac_pct": round(100 * valid_frac, 1),
        "base_time": C.BASE_TIMESTAMP, "cycle_s": C.CYCLE_SECONDS,
        "center": [(C.FIELD["lat_s"] + C.FIELD["lat_n"]) / 2, (C.FIELD["lon_w"] + C.FIELD["lon_e"]) / 2],
        "bounds": bounds,
    }

    # --- выгрузка для веб-визуализации (самодостаточный JS, без сервера) ---
    roads_path = os.path.join(C.DATA_DIR, "roads.geojson")
    roads = json.load(open(roads_path, encoding="utf-8")) if os.path.exists(roads_path) else None
    payload = {"meta": meta, "layers": layers, "points": points_geojson,
               "correlations": {k: v for k, v in correlations.items() if k != "image"},
               "field": json.load(open(os.path.join(C.DATA_DIR, "field.geojson"), encoding="utf-8")),
               "park": json.load(open(os.path.join(C.DATA_DIR, "park.geojson"), encoding="utf-8")),
               "roads": roads}
    js_path = os.path.join(C.WEB_DIR, "layers_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.AGROGEO = " + json.dumps(payload, ensure_ascii=False) + ";\n")

    # stats.json + correlations image отдельно
    with open(os.path.join(C.OUT_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "accuracy": accuracy,
                   "correlations": {k: v for k, v in correlations.items() if k != "image"}},
                  f, ensure_ascii=False, indent=2)

    # авто-отчёт по полю (HTML)
    write_report(meta, layers, accuracy, correlations)

    print(f"OK analyze: {len(cal_df)}/{n_raw} точек (valid {100*valid_frac:.1f}%), "
          f"PCA(2)={100*correlations['pca_first2']:.1f}%, Moran's I(N)={mi_n:.2f}")
    print(f"  -> {js_path}")
    return payload


def write_report(meta, layers, accuracy, correlations):
    rows = "".join(
        f"<tr><td>{l['name']}</td><td>{l['min']}…{l['max']} {l['unit']}</td>"
        f"<td>{l['mean']} {l['unit']}</td><td>±{accuracy[l['key']]['rel_pct']}%</td></tr>"
        for l in layers)
    tp = "".join(f"<li>{p['a'].upper()}–{p['b'].upper()}: r = {p['r']}</li>" for p in correlations["top_pairs"])
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>Отчёт по полю — {meta['park']}</title>
<style>body{{font-family:'Segoe UI',Arial,sans-serif;max-width:900px;margin:24px auto;color:#1a2330;line-height:1.5}}
h1{{font-size:20px}}h2{{font-size:16px;border-bottom:2px solid #2E75B6;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border:1px solid #b8c2cc;padding:6px 10px;font-size:14px;text-align:left}}
th{{background:#DCE6F1}}img{{max-width:100%;border:1px solid #ccc}} .grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.k{{font-size:12px;color:#555}} .v{{font-size:18px;font-weight:bold}}</style></head><body>
<h1>Автоматический отчёт по агрохимическому обследованию поля</h1>
<p><b>Объект:</b> {meta['park']} · <b>Договор:</b> {meta['contract']} · <b>Площадь:</b> {meta['field_area_ha']} га ·
<b>Старт прохода:</b> {meta['base_time']}</p>
<div class="grid">
<div><div class="k">Точек измерений (после очистки)</div><div class="v">{meta['n_clean']} / {meta['n_raw']}</div></div>
<div><div class="k">Доля валидных измерений</div><div class="v">{meta['valid_frac_pct']} %</div></div>
<div><div class="k">Цикл замера</div><div class="v">{meta['cycle_s']} с</div></div>
</div>
<h2>Сводка по 7 метрикам</h2>
<table><tr><th>Метрика</th><th>Диапазон по полю</th><th>Среднее</th><th>Отн. ошибка (кросс-валидация)</th></tr>{rows}</table>
<p class="k">Интерполяция — ординарный кригинг; отн. ошибка = LOO-RMSE / среднее.</p>
<h2>Корреляционный анализ</h2>
<p>Первые две главные компоненты (PCA) объясняют <b>{100*correlations['pca_first2']:.1f} %</b> дисперсии.
Индекс пространственной автокорреляции Moran's I (азот) = <b>{correlations['morans_I_n']}</b>.</p>
<p>Наиболее сильные связи метрик:</p><ul>{tp}</ul>
<img src="correlations.png" alt="Корреляционная матрица">
<h2>Тематические слои</h2>
<div class="grid">{''.join(f'<div><div class="k">{l["name"]}</div><img src="layers/{l["key"]}.png"></div>' for l in layers)}</div>
<p class="k">Интерактивная карта с 7 слоями — web/index.html.</p>
</body></html>"""
    with open(os.path.join(C.OUT_DIR, "field_report.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
