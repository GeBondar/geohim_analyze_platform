# -*- coding: utf-8 -*-
"""Полный конвейер платформы (реальные данные SoilGrids):
получение данных -> хранилище -> анализ -> выгрузка для веб-карты.

Сетевой шаг (fetch_real_data) долгий из-за лимитов API. Если данные уже
получены (data/raw_measurements.csv) — запускайте только storage+analyze:
    python -c "import storage,analyze; storage.build(); analyze.main()"
"""
import sys
import storage, analyze

if __name__ == "__main__":
    if "--skip-fetch" not in sys.argv:
        import fetch_real_data
        print("== 1/3 Получение РЕАЛЬНЫХ данных SoilGrids (КП п.1) ==")
        fetch_real_data.main()
    print("== 2/3 Загрузка в систему хранения (КП п.1) ==")
    storage.build()
    print("== 3/3 Анализ, интерполяция, корреляции, слои (КП пп.2,5) ==")
    analyze.main()
    print("\nГотово. Откройте web/index.html для интерактивной карты (КП пп.3,4).")
