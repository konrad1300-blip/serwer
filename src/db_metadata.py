"""Metadata aplikacji w tabeli `app_metadata` (SQLite).

Przechowuje informacje między sesjami UI, m.in. datę ostatniego odświeżenia
danych MES z ERP, tryb (full/incremental) oraz liczbę wierszy w pullu.

Wszystkie operacje są idempotentne — tabela tworzona w razie potrzeby.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.config import DB_PATH


def _resolve_path(db_path: Optional[Path]) -> Path:
    return Path(db_path) if db_path else DB_PATH


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Tworzy tabelę app_metadata, jeśli jeszcze nie istnieje."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)


def set_metadata(key: str, value: str, db_path: Optional[Path] = None) -> None:
    """Zapisuje/aktualizuje wartość klucza w app_metadata."""
    path = _resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        _ensure_table(conn)
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT OR REPLACE INTO app_metadata (key, value, updated_at) VALUES (?, ?, ?);",
            (key, value, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_metadata(key: str, db_path: Optional[Path] = None) -> Optional[str]:
    """Zwraca wartość klucza lub None, jeśli brak / plik nie istnieje."""
    path = _resolve_path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    try:
        _ensure_table(conn)
        cur = conn.execute("SELECT value FROM app_metadata WHERE key = ?;", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_refresh_info(mode: str, rows_count: int, db_path: Optional[Path] = None) -> None:
    """
    Zapisuje komplet informacji o ostatnim odświeżeniu z ERP:
    datę, tryb ('full'/'incremental') oraz liczbę wierszy pobranych w pullu.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    set_metadata("last_refresh_at", timestamp, db_path)
    set_metadata("last_refresh_mode", mode, db_path)
    set_metadata("last_refresh_rows", str(rows_count), db_path)


def get_refresh_info(db_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """Zwraca dict z kluczami last_refresh_at / last_refresh_mode / last_refresh_rows."""
    return {
        "last_refresh_at": get_metadata("last_refresh_at", db_path),
        "last_refresh_mode": get_metadata("last_refresh_mode", db_path),
        "last_refresh_rows": get_metadata("last_refresh_rows", db_path),
    }