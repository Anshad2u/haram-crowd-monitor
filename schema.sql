PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at_utc TEXT NOT NULL,
    fetched_at_saudi TEXT NOT NULL,
    source_url TEXT NOT NULL,
    request_status INTEGER,
    raw_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    area_type TEXT NOT NULL,
    area_key TEXT NOT NULL,
    area_name_en TEXT NOT NULL,
    area_name_ar TEXT,
    level_code TEXT,
    status_code INTEGER NOT NULL,
    status_label_en TEXT NOT NULL,
    color_en TEXT NOT NULL,
    is_available INTEGER NOT NULL,
    time_expect_minutes INTEGER,
    est_min_minutes INTEGER,
    est_max_minutes INTEGER,
    est_mid_minutes REAL,
    gates_csv TEXT,
    source_updated_at TEXT,
    observed_at_utc TEXT NOT NULL,
    observed_at_saudi TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES crawl_runs(run_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_observations_run_location
ON observations(run_id, location_id);

CREATE INDEX IF NOT EXISTS idx_observations_utc
ON observations(observed_at_utc);

CREATE INDEX IF NOT EXISTS idx_observations_saudi
ON observations(observed_at_saudi);

CREATE INDEX IF NOT EXISTS idx_observations_area
ON observations(area_type, area_key);

CREATE VIEW IF NOT EXISTS v_observations_en AS
SELECT
    observed_at_saudi,
    area_type,
    area_name_en,
    level_code,
    status_label_en,
    color_en,
    est_min_minutes,
    est_max_minutes,
    gates_csv
FROM observations;

CREATE VIEW IF NOT EXISTS v_hourly_area_stats AS
SELECT
    area_type,
    area_name_en,
    CAST(strftime('%H', observed_at_saudi) AS INTEGER) AS hour_of_day,
    COUNT(*) AS samples,
    ROUND(AVG(status_code), 3) AS avg_status_code,
    ROUND(AVG(est_mid_minutes), 2) AS avg_est_minutes,
    ROUND(SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) AS availability_ratio
FROM observations
GROUP BY area_type, area_name_en, hour_of_day;

CREATE VIEW IF NOT EXISTS v_daily_area_stats AS
SELECT
    date(observed_at_saudi) AS day,
    area_type,
    area_name_en,
    COUNT(*) AS samples,
    ROUND(AVG(status_code), 3) AS avg_status_code,
    ROUND(AVG(est_mid_minutes), 2) AS avg_est_minutes,
    ROUND(SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) AS availability_ratio
FROM observations
GROUP BY day, area_type, area_name_en;
