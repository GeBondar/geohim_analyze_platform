# -*- coding: utf-8 -*-
"""Генерация иллюстраций платформы: архитектура, ETL-конвейер, сравнение IDW/кригинг.
Сохраняет в ../assets и ../output для встраивания в отчёт и README.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import config as C
import storage, analyze

ASSETS = os.path.join(C.ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)


def _box(ax, x, y, w, h, title, lines, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
                                linewidth=1.3, edgecolor="#2E5070", facecolor=fc))
    ax.text(x + w/2, y + h - 0.07, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color="#16324f")
    ax.text(x + w/2, y + h - 0.20, "\n".join(lines), ha="center", va="top", fontsize=8.2, color="#23303d")


def _arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 linewidth=1.4, color="#5a6b7b"))


def fig_architecture():
    fig, ax = plt.subplots(figsize=(9.2, 3.4)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.4); ax.axis("off")
    y, h = 0.7, 2.0
    _box(ax, 0.1, y, 2.2, h, "Источники данных", ["SoilGrids (ISRIC)", "OSM — дороги", "Прибор: EC, T, P, K"], "#eaf2fb")
    _box(ax, 2.7, y, 2.2, h, "Хранение", ["PostgreSQL + PostGIS", "+ TimescaleDB", "SQLite (демо)"], "#e8f5ec")
    _box(ax, 5.3, y, 2.2, h, "Анализ", ["Очистка / QC", "IDW · кригинг", "корреляции, PCA,", "Moran's I"], "#fbf0e6")
    _box(ax, 7.9, y, 2.0, h, "Визуализация", ["Leaflet (11 слоёв)", "градиентные карты", "авто-отчёт"], "#f2e9fb")
    for x1, x2 in [(2.3, 2.7), (4.9, 5.3), (7.5, 7.9)]:
        _arrow(ax, x1, y + h/2, x2, y + h/2)
    ax.text(5, 3.25, "Архитектура платформы «АгроГео»", ha="center", fontsize=11.5, fontweight="bold", color="#16324f")
    fig.tight_layout(); p = os.path.join(ASSETS, "fig_architecture.png"); fig.savefig(p, dpi=150); plt.close(fig)
    print("  ", p)


def fig_etl():
    stages = ["Получение\n(SoilGrids)", "Фильтр дорог\n(OSM)", "Слои прибора\nEC/T/P/K",
              "Загрузка\nв БД", "Очистка\nQC", "Интерполяция\n(кригинг)", "Корреляции\nPCA · Moran's I", "Карты\n+ отчёт"]
    fig, ax = plt.subplots(figsize=(11.5, 2.2)); n = len(stages)
    ax.set_xlim(0, n); ax.set_ylim(0, 2); ax.axis("off")
    cols = ["#eaf2fb", "#eaf2fb", "#fdeede", "#e8f5ec", "#fbf0e6", "#fbf0e6", "#f2e9fb", "#f2e9fb"]
    w = 0.86
    for i, s in enumerate(stages):
        ax.add_patch(FancyBboxPatch((i + (1-w)/2, 0.5), w, 1.0, boxstyle="round,pad=0.02,rounding_size=0.05",
                                    linewidth=1.2, edgecolor="#2E5070", facecolor=cols[i]))
        ax.text(i + 0.5, 1.0, s, ha="center", va="center", fontsize=8.6, color="#16324f")
        if i < n - 1:
            _arrow(ax, i + 0.5 + w/2, 1.0, i + 1 + (1-w)/2, 1.0)
    ax.text(n/2, 1.85, "Конвейер обработки данных (ETL)", ha="center", fontsize=11, fontweight="bold", color="#16324f")
    fig.tight_layout(); p = os.path.join(ASSETS, "fig_etl.png"); fig.savefig(p, dpi=150); plt.close(fig)
    print("  ", p)


def fig_idw_vs_kriging():
    df = storage.load_measurements(); d, _ = analyze.clean(df); d = analyze.calibrate(d)
    S = analyze.to_meters(d["lon"], d["lat"]); z = d["n"].to_numpy()
    gx = np.linspace(C.FIELD["lon_w"], C.FIELD["lon_e"], C.GRID_NX)
    gy = np.linspace(C.FIELD["lat_n"], C.FIELD["lat_s"], C.GRID_NY)
    GX, GY = np.meshgrid(gx, gy); G = analyze.to_meters(GX.ravel(), GY.ravel())
    gi = analyze.idw_grid(S, z, G).reshape(C.GRID_NY, C.GRID_NX)
    gk = analyze.krige_grid(S, z, G).reshape(C.GRID_NY, C.GRID_NX)
    ri = analyze.loo_rmse(S, z, "idw"); rk = analyze.loo_rmse(S, z, "kriging")
    vmin, vmax = min(gi.min(), gk.min()), max(gi.max(), gk.max())
    fig, axs = plt.subplots(1, 2, figsize=(9.0, 4.0))
    for ax, g, ttl in [(axs[0], gi, f"IDW (LOO-RMSE = {ri:.3f})"), (axs[1], gk, f"Ординарный кригинг (LOO-RMSE = {rk:.3f})")]:
        im = ax.imshow(g, cmap="YlGn", vmin=vmin, vmax=vmax)
        ax.scatter((d["lon"]-C.FIELD["lon_w"])/(C.FIELD["lon_e"]-C.FIELD["lon_w"])*C.GRID_NX,
                   (C.FIELD["lat_n"]-d["lat"])/(C.FIELD["lat_n"]-C.FIELD["lat_s"])*C.GRID_NY,
                   s=8, facecolors="none", edgecolors="#333", linewidths=0.5)
        ax.set_title(ttl, fontsize=10); ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Сравнение методов интерполяции — азот (N), г/кг", fontsize=11.5, fontweight="bold")
    fig.colorbar(im, ax=axs, fraction=0.046, pad=0.04)
    p = os.path.join(ASSETS, "fig_idw_vs_kriging.png"); fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig)
    print(f"   IDW RMSE={ri:.3f}  Кригинг RMSE={rk:.3f}")
    print("  ", p)


def fig_web_ui():
    """Схема веб-интерфейса: панель слоёв + тематическая карта (азот)."""
    import matplotlib.image as mpimg
    df = storage.load_measurements(); d, _ = analyze.clean(df); d = analyze.calibrate(d)
    npng = os.path.join(C.OUT_DIR, "layers", "n.png")
    fig = plt.figure(figsize=(11.0, 5.6))
    fig.patch.set_facecolor("white")
    # левая панель
    axp = fig.add_axes([0.0, 0.0, 0.28, 1.0]); axp.set_xlim(0, 1); axp.set_ylim(0, 1); axp.axis("off")
    axp.add_patch(plt.Rectangle((0, 0), 1, 1, color="#0f2740"))
    axp.text(0.06, 0.95, "АгроГео", color="#e8eef5", fontsize=15, fontweight="bold")
    axp.text(0.06, 0.905, "Платформа геохимического анализа почвы", color="#9fb6cf", fontsize=7.5)
    axp.text(0.06, 0.85, "СЛОИ: 7 реальных (SoilGrids) + 4 прибора", color="#7fa8d0", fontsize=7.2)
    real = ["pH", "Влажность (VWC)", "Азот (N)", "Орг. углерод (SOC)", "ЕКО (CEC)", "Глина", "Песок"]
    dev = ["Солёность (EC) · прибор", "Температура · прибор", "Фосфор (P) · прибор", "Калий (K) · прибор"]
    y = 0.81
    for i, name in enumerate(real + dev):
        is_dev = i >= len(real)
        active = (name == "Азот (N)")
        fc = "#2E75B6" if active else ("#17324d")
        axp.add_patch(plt.Rectangle((0.06, y - 0.035), 0.88, 0.04, color=fc, ec="#2a4a6a", lw=0.6))
        if is_dev:
            axp.add_patch(plt.Rectangle((0.06, y - 0.035), 0.02, 0.04, color="#e0a13a"))
        axp.text(0.10, y - 0.015, name, color="#ffffff" if active else "#d7e3f0", fontsize=7.2, va="center")
        y -= 0.05
    # легенда
    axp.text(0.06, y - 0.01, "Азот общий (N), г/кг", color="#e8eef5", fontsize=8, fontweight="bold")
    grad = np.linspace(0, 1, 200).reshape(1, -1)
    axl = fig.add_axes([0.07, (y - 0.06), 0.20, 0.022]); axl.imshow(grad, aspect="auto", cmap="YlGn"); axl.axis("off")
    axp.text(0.06, y - 0.085, "8.9            10.2            11.6", color="#9fb6cf", fontsize=6.5)
    axp.text(0.06, y - 0.12, "● SoilGrids (ISRIC) — реальные данные", color="#aee0c0", fontsize=6.8)
    axp.text(0.06, y - 0.155, "Кросс-валидация (кригинг): ±5.07%", color="#7fc6a0", fontsize=6.8)
    for j, line in enumerate(["Объект: НП «Лосиный остров», Москва", "Участок 311 га · 32 точки · валидных 100%",
                              "PCA (2): 50.3% · Moran's I (N): 0.39", "SOC–глина −0.76 · ЕКО–песок −0.62"]):
        axp.text(0.06, y - 0.21 - j*0.038, line, color="#cfdcea", fontsize=6.8)
    # карта
    axm = fig.add_axes([0.30, 0.04, 0.68, 0.92])
    img = mpimg.imread(npng)
    axm.imshow(img, extent=[0, C.GRID_NX, 0, C.GRID_NY], origin="upper", aspect="auto")
    px = (d["lon"] - C.FIELD["lon_w"]) / (C.FIELD["lon_e"] - C.FIELD["lon_w"]) * C.GRID_NX
    py = (d["lat"] - C.FIELD["lat_s"]) / (C.FIELD["lat_n"] - C.FIELD["lat_s"]) * C.GRID_NY
    axm.scatter(px, py, s=14, facecolors="none", edgecolors="#10202f", linewidths=0.7)
    axm.add_patch(plt.Rectangle((0, 0), C.GRID_NX, C.GRID_NY, fill=False, ec="#ff3d00", lw=1.6))
    axm.set_xticks([]); axm.set_yticks([])
    axm.set_title("Тематическая карта: Азот (N) — реальные данные SoilGrids", fontsize=10, color="#16324f")
    p = os.path.join(ASSETS, "fig_web_ui.png"); fig.savefig(p, dpi=150, facecolor="white"); plt.close(fig)
    print("  ", p)


if __name__ == "__main__":
    print("Генерация рисунков:")
    fig_architecture(); fig_etl(); fig_idw_vs_kriging(); fig_web_ui()
    print("Готово.")
