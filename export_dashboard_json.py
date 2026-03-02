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


def normalize_area_display(area_type: str, area_name_en: str, level_code: str | None) -> tuple[str, str | None]:
    """Apply requested floor naming convention for Tawaf levels."""
    if area_type != "tawaf":
        return area_name_en, level_code

    if area_name_en == "Ground Floor Tawaf":
        return "First Floor Tawaf", "1"
    if area_name_en == "First Floor Tawaf":
        return "Second Floor Tawaf", "2"
    if area_name_en == "Roof Tawaf":
        return "Roof Tawaf", "3"
    if area_name_en == "Mataf Courtyard (Around Kaaba)":
        return "Mataf Ground Floor (Around Kaaba)", "G"

    return area_name_en, level_code


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

    items = []
    for row in rows:
        area_name, level_code = normalize_area_display(row[0], row[1], row[2])
        items.append(
            {
                "areaType": row[0],
                "areaNameEn": area_name,
                "levelCode": level_code,
                "statusLabel": row[3],
                "color": row[4],
                "estimatedMin": row[5],
                "estimatedMax": row[6],
                "gates": row[7],
            }
        )
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
    area_rank = []
    for row in cur.fetchall():
        normalized_name, _ = normalize_area_display("tawaf" if "Tawaf" in row[0] or "Mataf" in row[0] else "sai", row[0], None)
        area_rank.append(
            {
                "areaNameEn": normalized_name,
                "avgStatus": row[1],
                "avgMinutes": row[2],
                "availabilityPct": row[3],
                "samples": row[4],
            }
        )

    return {"period": period, "bestHours": best_hours, "areaRank": area_rank}


def export_history(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM crawl_runs")
    run_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM observations")
    observation_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT
            r.run_id,
            r.fetched_at_saudi,
            o.area_type,
            o.area_name_en,
            o.level_code,
            o.status_label_en,
            o.color_en,
            o.est_min_minutes,
            o.est_max_minutes,
            o.gates_csv
        FROM crawl_runs r
        JOIN observations o ON o.run_id = r.run_id
        ORDER BY r.run_id DESC, o.location_id ASC
        """
    )

    runs_map: dict[int, dict] = {}
    for row in cur.fetchall():
        run_id = row[0]
        if run_id not in runs_map:
            runs_map[run_id] = {
                "runId": run_id,
                "fetchedAtSaudi": row[1],
                "items": [],
            }
        area_name, level_code = normalize_area_display(row[2], row[3], row[4])
        runs_map[run_id]["items"].append(
            {
                "areaType": row[2],
                "areaNameEn": area_name,
                "levelCode": level_code,
                "statusLabel": row[5],
                "color": row[6],
                "estimatedMin": row[7],
                "estimatedMax": row[8],
                "gates": row[9],
            }
        )

    runs = list(runs_map.values())
    return {
        "runCount": run_count,
        "observationCount": observation_count,
        "runs": runs,
    }


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
        history = export_history(conn)
    finally:
        conn.close()

    write_json(out / "latest.json", latest)
    write_json(out / "analysis-week.json", week)
    write_json(out / "analysis-month.json", month)
    write_json(out / "analysis-year.json", year)
    write_json(out / "history.json", history)
    print(f"Exported dashboard JSON into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
