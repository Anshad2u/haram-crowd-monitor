#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data"

CRON_CMD="5 * * * * /bin/bash $PROJECT_DIR/publish_dashboard.sh"
EXISTING_CRON="$(crontab -l 2>/dev/null || true)"

if grep -Fq "$PROJECT_DIR/publish_dashboard.sh" <<< "$EXISTING_CRON"; then
  echo "Publish cron job already exists."
  exit 0
fi

{
  echo "$EXISTING_CRON"
  echo "$CRON_CMD"
} | crontab -

echo "Installed publish cron job:"
echo "$CRON_CMD"
