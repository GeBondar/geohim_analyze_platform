-- ============================================================================
-- АгроГео · КП Этап 2, работа 1: система хранения геохимических данных
-- ПРОДАКШЕН-СХЕМА: PostgreSQL 16 + PostGIS 3.4 + TimescaleDB 2.x
-- (в демо-сборке платформа использует встроенный SQLite, см. src/storage.py)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Справочник кампаний/маршрутов робота
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id   serial PRIMARY KEY,
    contract_no   text       NOT NULL DEFAULT '17098ГУ/2021',
    field_name    text       NOT NULL,
    started_at    timestamptz NOT NULL,
    note          text
);

-- Основная гипертаблица измерений (пространство + время)
CREATE TABLE IF NOT EXISTS measurements (
    measurement_id bigserial   NOT NULL,
    campaign_id    int         REFERENCES campaigns(campaign_id),
    ts             timestamptz NOT NULL,           -- время замера
    geom           geometry(Point, 4326) NOT NULL, -- координата точки (WGS84)
    ph             real,                            -- ед. pH
    ec             real,                            -- дС/м
    vwc            real,                            -- %
    t              real,                            -- °C
    n              real,                            -- мг/кг
    p              real,                            -- мг/кг
    k              real,                            -- мг/кг
    qc_flag        smallint DEFAULT 1,              -- 1=ok, 0=подозрительное
    calib_level    smallint DEFAULT 3,             -- уровень калибровки 1..3
    PRIMARY KEY (measurement_id, ts)
);

-- Гипертаблица по времени (TimescaleDB)
SELECT create_hypertable('measurements', 'ts', if_not_exists => TRUE);

-- Пространственный индекс (PostGIS, GiST)
CREATE INDEX IF NOT EXISTS idx_measurements_geom ON measurements USING gist (geom);
CREATE INDEX IF NOT EXISTS idx_measurements_campaign ON measurements (campaign_id, ts DESC);

-- Сжатие временных рядов (горячие данные 90 суток без сжатия, далее — сжатие)
ALTER TABLE measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'campaign_id'
);
SELECT add_compression_policy('measurements', INTERVAL '90 days');

-- Непрерывный агрегат: суточные средние по метрикам (витрина для дашбордов)
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_daily
WITH (timescaledb.continuous) AS
SELECT campaign_id,
       time_bucket('1 day', ts) AS day,
       avg(ph) ph, avg(ec) ec, avg(vwc) vwc, avg(t) t,
       avg(n) n, avg(p) p, avg(k) k,
       count(*) n_points
FROM measurements
GROUP BY campaign_id, time_bucket('1 day', ts);

-- Пример пространственно-временной выборки (по bbox и периоду):
-- SELECT * FROM measurements
--  WHERE ts BETWEEN :t1 AND :t2
--    AND ST_Within(geom, ST_MakeEnvelope(:lon_w,:lat_s,:lon_e,:lat_n, 4326));
