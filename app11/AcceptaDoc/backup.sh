#!/bin/bash
# backup.sh — dzienny backup AcceptaDoc (baza + PDF-y), keep-7.
# Uruchamiany przez cron: 30 2 * * * /home/konrad/apps/app11/AcceptaDoc/backup.sh
set -euo pipefail

APP_DIR="$HOME/apps/app11/AcceptaDoc"
BACKUP_DIR="$HOME/backups/acceptadoc"
DB_PATH="$APP_DIR/instance/acceptadoc.db"
DOCS_DIR="$APP_DIR/data/documents"
KEEP=7
LOG="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"

TS=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$BACKUP_DIR/acceptadoc-$TS.tar.gz"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

echo "[$(date '+%Y-%m-%d %H:%M:%S')] START → $ARCHIVE" >> "$LOG"

# 1. Spójna kopia bazy (bezpieczne przy WAL i działającej aplikacji)
sqlite3 "$DB_PATH" ".backup '$STAGE/acceptadoc.db'"

# 2. Kontrola spójności — jeśli kopia jest uszkodzona, archiwum NIE powstanie
RESULT=$(sqlite3 "$STAGE/acceptadoc.db" "PRAGMA integrity_check;")
if [ "$RESULT" != "ok" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BŁĄD: integrity_check → $RESULT" >> "$LOG"
    exit 1
fi

# 3. PDF-y (jeśli katalog istnieje)
if [ -d "$DOCS_DIR" ]; then
    cp -a "$DOCS_DIR" "$STAGE/documents"
fi

# 4. Archiwum — atomowo: najpierw .tmp, potem rename
tar czf "$ARCHIVE.tmp" -C "$STAGE" .
mv "$ARCHIVE.tmp" "$ARCHIVE"

# 5. Rotacja — zostaw 7 najnowszych, usuń starsze
ls -1t "$BACKUP_DIR"/acceptadoc-*.tar.gz 2>/dev/null \
    | tail -n +$((KEEP + 1)) \
    | xargs -r rm -f

SIZE=$(du -h "$ARCHIVE" | cut -f1)
COUNT=$(ls -1 "$BACKUP_DIR"/acceptadoc-*.tar.gz 2>/dev/null | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: $(basename "$ARCHIVE") ($SIZE, archiwów: $COUNT)" >> "$LOG"
