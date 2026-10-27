#!/usr/bin/env bash
# Wrapper crona dla nocnego odświeżania bazy MES.
# Uruchamiany o 1:00 UTC z crontab użytkownika 'konrad'.
#
# Ręczne uruchomienie:  ./scripts/refresh_nightly.sh
#
# flock -n: jeśli inny run wciąż trwa, nowy jest natychmiast pomijany
# (żaden proces nie czeka — nie kumulują się zadania).
#
# UWAGA o przekierowaniach:
# - stderr → wrapper log (tylko tracebacki z fazy startu Pythona: brak venv,
#   import error, itp. — zanim _setup_logging() przejmie kontrolę),
# - stdout NIE jest przekierowywany — trafia na konsolę (interaktywnie)
#   lub do /dev/null (cron). W trybie cron Pythonowe logi i tak trafiają
#   do data/logs/nightly_refresh.log przez RotatingFileHandler.

set -euo pipefail

PROJECT_DIR="/home/konrad/apps/app10"
VENV_PY="$PROJECT_DIR/venv/bin/python"
LOCK_FILE="/tmp/plandeka_refresh.lock"
WRAPPER_LOG="$PROJECT_DIR/data/logs/nightly_refresh_wrapper.log"

mkdir -p "$(dirname "$WRAPPER_LOG")"

# Tylko stderr → wrapper log; stdout zostaje nietknięty.
exec 2>> "$WRAPPER_LOG"

# Linia startowa jawnie na stderr (żeby trafiła do wrapper logu niezależnie
# od tego, gdzie idzie stdout). W terminalu też będzie widoczna.
echo "=== $(date -Iseconds) start wrappera ===" >&2

cd "$PROJECT_DIR"

# flock -n: nie czekaj, jeśli inny run trzyma lock — po prostu pomiń.
exec flock -n "$LOCK_FILE" "$VENV_PY" -m scripts.nightly_refresh