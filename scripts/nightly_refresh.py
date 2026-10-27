"""Nocne odświeżanie bazy MES z ERP XL (uruchamiane przez cron).

Pipeline (każdy krok raportowany osobno, błąd nie blokuje kolejnych):
1. Backup bazy SQLite do data/backups/ (retencja 7 dni).
2. Test połączenia z ERP XL (3 próby co 10 min).
3. MES: MESProcessor().process_and_save(mode='auto').
4. BOM: BOMProcessor().process_and_save() (pełny pull).
5. Reindeksacja DXF — tylko jeśli katalog dxf/ zawiera co najmniej 1 plik.

Kod wyjścia: 0 = wszystkie kroki OK, 1 = co najmniej jeden błąd.

Logi: data/logs/nightly_refresh.log (rotacja 5 MB × 7 plików).
Print() z procesorów jest przechwytywany i też trafia do tego logu.
"""
from __future__ import annotations

import logging
import sqlite3
import sys
import time
import warnings
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import BASE_DIR, DB_PATH, DXF_DIR
from src.processors.bom_processor import BOMProcessor
from src.processors.data_source import ERPDataSource
from src.processors.dxf_processor import index_dxf_directory_to_db
from src.processors.mes_processor import MESProcessor


# Wyciszamy konkretny UserWarning z pandas o SQLAlchemy — dotyczy `pd.read_sql`
# wywoływanego w `data_source.py` z surowym połączeniem pyodbc. Pipeline działa
# poprawnie, a warning w logu wygląda jak błąd (bo warnings.warn pisze na stderr,
# który przechwytujemy jako ERROR). Filtrujemy precyzyjnie — inne warningi
# (i prawdziwe błędy) dalej trafiają do logu.
warnings.filterwarnings(
    "ignore",
    message=r"pandas only supports SQLAlchemy connectable.*",
    category=UserWarning,
)


# --- Konfiguracja -----------------------------------------------------------
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_PATH = LOG_DIR / "nightly_refresh.log"
BACKUP_DIR = BASE_DIR / "data" / "backups"
BACKUP_RETENTION_DAYS = 7
ERP_RETRY_ATTEMPTS = 3
ERP_RETRY_DELAY_SECONDS = 600  # 10 minut

logger = logging.getLogger("nightly_refresh")


def _setup_logging() -> None:
    """
    Konfiguruje logger: rotujący plik + oryginalny stdout, oraz przechwytuje
    print() z procesorów (MESProcessor/BOMProcessor/dxf_processor), żeby ich
    komunikaty też trafiły do rotującego pliku — a nie tylko do /dev/null crona.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=7, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # sys.__stdout__ = ORYGINALNY stdout (nie podmieniony poniżej) — brak rekurencji.
    stream_handler = logging.StreamHandler(sys.__stdout__)
    stream_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    class _LoggerWriter:
        """Minimalny adapter: write() z print() → logger, bez pętli zwrotnej."""

        def __init__(self, log: logging.Logger, level: int):
            self._log = log
            self._level = level

        def write(self, msg: str) -> None:
            if msg and msg.strip():
                self._log.log(self._level, msg.rstrip())

        def flush(self) -> None:
            pass

    sys.stdout = _LoggerWriter(logger, logging.INFO)
    sys.stderr = _LoggerWriter(logger, logging.ERROR)


# --- Backup ----------------------------------------------------------------
def _backup_database() -> Path:
    """
    Kopiuje bazę SQLite do data/backups/ z timestampem. Używa sqlite3.backup()
    (spójna kopia nawet przy aktywnych połączeniach Streamlita). Usuwa backupy
    starsze niż BACKUP_RETENTION_DAYS dni.

    :return: ścieżka nowego backupu.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"baza_mes_{stamp}.sqlite"

    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    size_mb = backup_path.stat().st_size / 1024 / 1024
    logger.info(f"Backup bazy: {backup_path.name} ({size_mb:.2f} MB)")

    cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
    for old in BACKUP_DIR.glob("baza_mes_*.sqlite"):
        try:
            mtime = datetime.fromtimestamp(old.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                old.unlink()
                logger.info(f"Usunięto stary backup: {old.name}")
            except OSError as ex:
                logger.warning(f"Nie udało się usunąć {old.name}: {ex}")

    return backup_path


# --- ERP test z retry ------------------------------------------------------
def _test_erp_with_retry() -> bool:
    """Testuje połączenie z ERP: do ERP_RETRY_ATTEMPTS prób co ERP_RETRY_DELAY_SECONDS."""
    erp = ERPDataSource()
    for attempt in range(1, ERP_RETRY_ATTEMPTS + 1):
        ok, msg = erp.test_connection()
        if ok:
            logger.info(f"ERP test OK (próba {attempt}/{ERP_RETRY_ATTEMPTS}): {msg}")
            return True
        logger.warning(f"ERP test FAIL (próba {attempt}/{ERP_RETRY_ATTEMPTS}): {msg}")
        if attempt < ERP_RETRY_ATTEMPTS:
            logger.info(f"Czekam {ERP_RETRY_DELAY_SECONDS} s przed kolejną próbą...")
            time.sleep(ERP_RETRY_DELAY_SECONDS)
    return False


# --- Kroki pipeline --------------------------------------------------------
def _step_mes() -> bool:
    """Pobiera MES z ERP i zapisuje do bazy w trybie 'auto'."""
    try:
        MESProcessor().process_and_save(mode="auto")
        logger.info("Krok MES: OK")
        return True
    except Exception as ex:
        logger.exception(f"Krok MES: BŁĄD — {ex}")
        return False


def _step_bom() -> bool:
    """Pobiera BOM z ERP (pełny pull) i zapisuje do bazy."""
    try:
        BOMProcessor().process_and_save()
        logger.info("Krok BOM: OK")
        return True
    except Exception as ex:
        logger.exception(f"Krok BOM: BŁĄD — {ex}")
        return False


def _step_dxf() -> bool:
    """
    Reindeksuje pliki DXF. Pomijany (z WARNING), gdy katalog dxf/ jest pusty
    lub nie istnieje — żeby nie wyczyścić product_dxf_features bez powodu.
    """
    if not DXF_DIR.exists():
        logger.warning("Krok DXF: katalog dxf/ nie istnieje — pomijam")
        return True

    dxf_files = [f for f in DXF_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".dxf"]
    if not dxf_files:
        logger.warning(
            "Krok DXF: brak plików .dxf — pomijam reindeksację "
            "(tabela product_dxf_features pozostaje nietknięta)"
        )
        return True

    try:
        count = index_dxf_directory_to_db()
        logger.info(f"Krok DXF: OK — {count} kodów z {len(dxf_files)} plików")
        return True
    except Exception as ex:
        logger.exception(f"Krok DXF: BŁĄD — {ex}")
        return False


# --- Main ------------------------------------------------------------------
def main() -> int:
    """Uruchamia nocne odświeżanie. Zwraca kod wyjścia (0 = pełny sukces)."""
    _setup_logging()
    started = datetime.now()
    logger.info("=" * 70)
    logger.info(f"Start nocnego odświeżania: {started.isoformat(timespec='seconds')}")

    if not DB_PATH.exists():
        logger.error(
            f"Baza SQLite nie istnieje: {DB_PATH}. Uruchom najpierw ręcznie "
            f"'Pobierz MES z ERP' w UI albo 'python main.py --rebuild-db'."
        )
        return 1

    # 1. Backup — jeśli padnie, przerywamy pipeline (ochrona danych).
    try:
        _backup_database()
    except Exception as ex:
        logger.exception(f"Backup bazy: BŁĄD — {ex}. Przerywam pipeline.")
        return 1

    # 2. Test ERP z retry — brak łączności = bez sensu próbować cokolwiek dalej.
    if not _test_erp_with_retry():
        logger.error("ERP niedostępne po wszystkich próbach. Przerywam.")
        return 1

    # 3-5. Pipeline — kroki niezależne, błąd jednego nie blokuje kolejnych.
    results = {
        "MES": _step_mes(),
        "BOM": _step_bom(),
        "DXF": _step_dxf(),
    }

    elapsed = (datetime.now() - started).total_seconds()
    if all(results.values()):
        logger.info(f"Zakończono pomyślnie w {elapsed:.1f} s.")
        return 0

    failed = [k for k, ok in results.items() if not ok]
    logger.error(
        f"Zakończono z błędami w krokach: {', '.join(failed)} "
        f"(czas: {elapsed:.1f} s)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())