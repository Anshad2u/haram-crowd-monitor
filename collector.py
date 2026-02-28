#!/usr/bin/env python3
"""Hourly collector for Tawaf/Sa'i crowd status.

Fetches live data from the same endpoint used by the official page,
normalizes it, and writes one snapshot into SQLite.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SOURCE_URL = "https://trasul.gph.gov.sa/haram-api/public/api/pry/TawafSaiStatus"
SAUDI_TZ = ZoneInfo("Asia/Riyadh")

STATUS_LABELS = {
    1: "Light",
    2: "Medium",
    3: "Heavy",
    4: "Not Available",
}

STATUS_COLORS = {
    1: "Green",
    2: "Brown / Orange",
    3: "Red",
    4: "Dark Grey",
}

# Canonical mapping based on live page JavaScript (locationMap)
LOCATION_MAP = {
    1: ("tawaf", "mataf_courtyard", "Mataf Courtyard (Around Kaaba)", "صحن الطواف", "G"),
    2: ("tawaf", "tawaf_ground_floor", "Ground Floor Tawaf", "مطاف الدور الارضي", "G"),
    3: ("tawaf", "tawaf_first_floor", "First Floor Tawaf", "مطاف الدور الاول", "1"),
    5: ("tawaf", "tawaf_roof", "Roof Tawaf", "سطح المطاف", "2"),
    7: ("sai", "sai_ground_floor", "Ground Floor Sa'i", "المسعى الدور الارضي", "G"),
    8: ("sai", "sai_first_floor", "First Floor Sa'i", "المسعى الدور الاول", "1"),
    10: ("sai", "sai_second_floor", "Second Floor Sa'i", "المسعى الدور الثاني", "2"),
}


@dataclass
class NormalizedRow:
    location_id: int
    area_type: str
    area_key: str
    area_name_en: str
    area_name_ar: str
    level_code: str
    status_code: int
    status_label_en: str
    color_en: str
    is_available: int
    time_expect_minutes: int | None
    est_min_minutes: int | None
    est_max_minutes: int | None
    est_mid_minutes: float | None
    gates_csv: str | None
    source_updated_at: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Tawaf/Sa'i status into SQLite")
    parser.add_argument(
        "--db",
        default="data/haram_crowd.db",
        help="Path to SQLite DB file (default: data/haram_crowd.db)",
    )
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Enable SSL certificate verification (off by default due endpoint chain issues)",
    )
    return parser.parse_args()


def ensure_db(conn: sqlite3.Connection, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()


def normalize_gates(door_no: str | None) -> str | None:
    if not door_no:
        return None
    numbers = re.findall(r"\d+", door_no)
    return ", ".join(numbers) if numbers else None


def normalize_row(row: dict[str, Any]) -> NormalizedRow | None:
    try:
        location_id = int(row["id"])
    except (KeyError, TypeError, ValueError):
        return None

    mapping = LOCATION_MAP.get(location_id)
    if not mapping:
        return None

    area_type, area_key, area_name_en, area_name_ar_default, level_code = mapping
    area_name_ar = str(row.get("location_name") or area_name_ar_default)

    status_code = int(row.get("status") or 4)
    status_label_en = STATUS_LABELS.get(status_code, "Unknown")
    color_en = STATUS_COLORS.get(status_code, "Unknown")

    time_expect_minutes = None
    est_min_minutes = None
    est_max_minutes = None
    est_mid_minutes = None
    is_available = 0 if status_code == 4 else 1

    if is_available:
        try:
            time_expect_minutes = int(row.get("time_expect"))
            est_min_minutes = time_expect_minutes - 5
            est_max_minutes = time_expect_minutes + 5
            est_mid_minutes = float(time_expect_minutes)
        except (TypeError, ValueError):
            pass

    gates_csv = normalize_gates(row.get("door_no"))

    return NormalizedRow(
        location_id=location_id,
        area_type=area_type,
        area_key=area_key,
        area_name_en=area_name_en,
        area_name_ar=area_name_ar,
        level_code=level_code,
        status_code=status_code,
        status_label_en=status_label_en,
        color_en=color_en,
        is_available=is_available,
        time_expect_minutes=time_expect_minutes,
        est_min_minutes=est_min_minutes,
        est_max_minutes=est_max_minutes,
        est_mid_minutes=est_mid_minutes,
        gates_csv=gates_csv,
        source_updated_at=row.get("updated_at"),
    )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    now_saudi = now_utc.astimezone(SAUDI_TZ)

    response = requests.get(SOURCE_URL, timeout=args.timeout, verify=args.verify_ssl)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected API response shape: expected list")

    normalized = [nr for r in payload if (nr := normalize_row(r)) is not None]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_db(conn, Path(__file__).with_name("schema.sql"))

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crawl_runs (fetched_at_utc, fetched_at_saudi, source_url, request_status, raw_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                now_saudi.strftime("%Y-%m-%d %H:%M:%S"),
                SOURCE_URL,
                response.status_code,
                len(payload),
            ),
        )
        run_id = cur.lastrowid

        for row in normalized:
            cur.execute(
                """
                INSERT INTO observations (
                    run_id, location_id, area_type, area_key, area_name_en, area_name_ar, level_code,
                    status_code, status_label_en, color_en, is_available,
                    time_expect_minutes, est_min_minutes, est_max_minutes, est_mid_minutes,
                    gates_csv, source_updated_at, observed_at_utc, observed_at_saudi
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    row.location_id,
                    row.area_type,
                    row.area_key,
                    row.area_name_en,
                    row.area_name_ar,
                    row.level_code,
                    row.status_code,
                    row.status_label_en,
                    row.color_en,
                    row.is_available,
                    row.time_expect_minutes,
                    row.est_min_minutes,
                    row.est_max_minutes,
                    row.est_mid_minutes,
                    row.gates_csv,
                    row.source_updated_at,
                    now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    now_saudi.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

        conn.commit()
        print(f"Stored run_id={run_id} with {len(normalized)} normalized rows into {db_path}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
