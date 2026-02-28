#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="$PROJECT_DIR/data/haram_crowd.db"
LOG_FILE="$PROJECT_DIR/logs/publish.log"

mkdir -p "$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

python3 collector.py --db "$DB_PATH" >> "$LOG_FILE" 2>&1
python3 export_dashboard_json.py --db "$DB_PATH" --out "$PROJECT_DIR/public/data" >> "$LOG_FILE" 2>&1

git add public/data/*.json
if git diff --cached --quiet; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') no dashboard JSON changes" >> "$LOG_FILE"
  exit 0
fi

git commit -m "Update dashboard data $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') dashboard data published" >> "$LOG_FILE"
