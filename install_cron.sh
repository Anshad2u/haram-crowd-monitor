#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3)"
DB_PATH="$PROJECT_DIR/data/haram_crowd.db"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/collector.log"

mkdir -p "$LOG_DIR" "$PROJECT_DIR/data"

CRON_CMD="0 * * * * $PYTHON_BIN $PROJECT_DIR/collector.py --db $DB_PATH >> $LOG_FILE 2>&1"

EXISTING_CRON="$(crontab -l 2>/dev/null || true)"
if grep -Fq "$PROJECT_DIR/collector.py" <<< "$EXISTING_CRON"; then
  echo "Cron job already exists."
  exit 0
fi

{
  echo "$EXISTING_CRON"
  echo "$CRON_CMD"
} | crontab -

echo "Installed hourly cron job:"
echo "$CRON_CMD"
