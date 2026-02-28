# Haram Crowd Monitor

Hourly collector for Mataf/Tawaf and Masaa/Sa'i crowd data.

## What It Stores

For each hourly snapshot, it stores:

- area (`Tawaf` / `Sa'i`)
- floor/location
- crowd status code and label
- color label (`Green`, `Brown/Orange`, `Red`, `Dark Grey`)
- expected duration (and min/max range)
- gates (for Tawaf locations)
- observation timestamp (UTC + Saudi)

## Data Source

Live API used by the official page JavaScript:

`https://trasul.gph.gov.sa/haram-api/public/api/pry/TawafSaiStatus`

## Setup

```bash
cd /home/anshad/haram-crowd-monitor
python3 -m pip install -r requirements.txt
```

## Run Collector Once

```bash
python3 collector.py --db data/haram_crowd.db
```

## Install Hourly Schedule

```bash
bash install_cron.sh
```

This adds:

`0 * * * * python3 /home/anshad/haram-crowd-monitor/collector.py --db /home/anshad/haram-crowd-monitor/data/haram_crowd.db`

## Analyze Best Times

```bash
python3 analyze.py --db data/haram_crowd.db --period week
python3 analyze.py --db data/haram_crowd.db --period month
python3 analyze.py --db data/haram_crowd.db --period year
```

## Useful SQL Queries

```sql
-- Best hours overall (lower status + lower duration is better)
SELECT
  CAST(strftime('%H', observed_at_saudi) AS INTEGER) AS hour_of_day,
  ROUND(AVG(status_code), 3) AS avg_status,
  ROUND(AVG(est_mid_minutes), 2) AS avg_minutes,
  COUNT(*) AS samples
FROM observations
WHERE observed_at_utc >= datetime('now', '-30 days')
  AND is_available = 1
GROUP BY hour_of_day
ORDER BY avg_status ASC, avg_minutes ASC, samples DESC;
```

```sql
-- Best hour per area
SELECT
  area_name_en,
  CAST(strftime('%H', observed_at_saudi) AS INTEGER) AS hour_of_day,
  ROUND(AVG(status_code), 3) AS avg_status,
  ROUND(AVG(est_mid_minutes), 2) AS avg_minutes,
  COUNT(*) AS samples
FROM observations
WHERE observed_at_utc >= datetime('now', '-30 days')
  AND is_available = 1
GROUP BY area_name_en, hour_of_day
HAVING samples >= 2
ORDER BY area_name_en, avg_status ASC, avg_minutes ASC;
```

## Notes

- Status mapping: `1=Light/Green`, `2=Medium/Brown-Orange`, `3=Heavy/Red`, `4=Not Available/Dark Grey`.
- If status is `Not Available`, time range is stored as `NULL`.
- Keep this running for at least 2-4 weeks to get meaningful monthly patterns.
