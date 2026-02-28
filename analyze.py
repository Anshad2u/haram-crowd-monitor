#!/usr/bin/env python3
"""Quick CLI analysis over hourly Tawaf/Sa'i observations."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

RANGE_SQL = {
    "week": "-7 days",
    "month": "-30 days",
    "year": "-365 days",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze best Umrah timing from collected data")
    parser.add_argument("--db", default="data/haram_crowd.db", help="SQLite DB path")
    parser.add_argument(
        "--period",
        choices=("week", "month", "year"),
        default="week",
        help="Time window for analysis",
    )
    return parser.parse_args()


def print_rows(title: str, rows: list[tuple]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not rows:
        print("No data yet.")
        return
    for row in rows:
        print(" | ".join(str(col) for col in row))


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    range_expr = RANGE_SQL[args.period]

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

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
            LIMIT 6
            """,
            (range_expr,),
        )
        best_overall = cur.fetchall()

        cur.execute(
            """
            SELECT
                area_name_en,
                CAST(strftime('%H', observed_at_saudi) AS INTEGER) AS hour_of_day,
                ROUND(AVG(status_code), 3) AS avg_status,
                ROUND(AVG(est_mid_minutes), 2) AS avg_minutes,
                COUNT(*) AS samples
            FROM observations
            WHERE observed_at_utc >= datetime('now', ?)
              AND is_available = 1
            GROUP BY area_name_en, hour_of_day
            ORDER BY area_name_en, avg_status ASC, avg_minutes ASC
            """,
            (range_expr,),
        )
        best_by_area = cur.fetchall()

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
            (range_expr,),
        )
        area_rank = cur.fetchall()
    finally:
        conn.close()

    print(f"Analysis period: {args.period}")
    print_rows("Best Hours Overall (Saudi local hour)", best_overall)
    print_rows("Best Hour By Area", best_by_area)
    print_rows("Area Ranking", area_rank)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
