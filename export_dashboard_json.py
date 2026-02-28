#!/usr/bin/env python3
"""Export SQLite data into static JSON files consumed by Vercel dashboard."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export dashboard JSON files")
    parser.add_argument("--db", default="data/haram_crowd.db", help="SQLite DB path")
    parser.add_argument("--out", default="public/data", help="Output directory for JSON")
    return parser.parse_args()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def period_expr(period: str) -> str:
    return {
        "week": "-7 days",
        "month": "-30 days",
        "year": "-365 days",
    }[period]


def export_latest(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT MAX(run_id) FROM crawl_runs")
    run_id = cur.fetchone()[0]
    if run_id is None:
        return {"runId": None, "fetchedAtSaudi": None, "items": []}

    cur.execute("SELECT fetched_at_saudi FROM crawl_runs WHERE run_id = ?", (run_id,))
    fetched_at_saudi = cur.fetchone()[0]

    cur.execute(
        """
        SELECT area_type, area_name_en, level_code, status_label_en, color_en,
               est_min_minutes, est_max_minutes, gates_csv
        FROM observations
        WHERE run_id = ?
        ORDER BY location_id
        """,
        (run_id,),
    )
    rows = cur.fetchall()

    items = [
        {
            "areaType": row[0],
            "areaNameEn": row[1],
            "levelCode": row[2],
            "statusLabel": row[3],
            "color": row[4],
            "estimatedMin": row[5],
            "estimatedMax": row[6],
            "gates": row[7],
        }
        for row in rows
    ]
    return {"runId": run_id, "fetchedAtSaudi": fetched_at_saudi, "items": items}


def export_period_analysis(conn: sqlite3.Connection, period: str) -> dict:
    cur = conn.cursor()
    expr = period_expr(period)

    cur.execute(
        """
        SELECT
            CAST(strftime('%H', observed_at_saudi) AS INTEGER) AS hour_of_day,
            ROUND(AVG(status_code), 3) AS avg_status,
            ROUND(AVG(est_mid_minutes), 2) AS avg_minutes,
            COUNT(*) AS samples
        FROM observations
        WHERE observed_at_utc >= datetime('now', ?)
          AND is_available = 1
        GROUP BY hour_of_day
        ORDER BY avg_status ASC, avg_minutes ASC, samples DESC
        LIMIT 12
        """,
        (expr,),
    )
    best_hours = [
        {"hour": row[0], "avgStatus": row[1], "avgMinutes": row[2], "samples": row[3]}
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT
            area_name_en,
            ROUND(AVG(status_code), 3) AS avg_status,
            ROUND(AVG(est_mid_minutes), 2) AS avg_minutes,
            ROUND(SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS availability_pct,
            COUNT(*) AS samples
        FROM observations
        WHERE observed_at_utc >= datetime('now', ?)
        GROUP BY area_name_en
        ORDER BY avg_status ASC, avg_minutes ASC
        """,
        (expr,),
    )
    area_rank = [
        {
            "areaNameEn": row[0],
            "avgStatus": row[1],
            "avgMinutes": row[2],
            "availabilityPct": row[3],
            "samples": row[4],
        }
        for row in cur.fetchall()
    ]

    return {"period": period, "bestHours": best_hours, "areaRank": area_rank}


def main() -> int:
    args = parse_args()
    db = Path(args.db).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()

    if not db.exists():
        raise FileNotFoundError(f"DB not found: {db}")

    conn = sqlite3.connect(db)
    try:
        latest = export_latest(conn)
        week = export_period_analysis(conn, "week")
        month = export_period_analysis(conn, "month")
        year = export_period_analysis(conn, "year")
    finally:
        conn.close()

    write_json(out / "latest.json", latest)
    write_json(out / "analysis-week.json", week)
    write_json(out / "analysis-month.json", month)
    write_json(out / "analysis-year.json", year)
    print(f"Exported dashboard JSON into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
