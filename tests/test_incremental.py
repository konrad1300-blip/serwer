"""Testy przyrostowego zapisu MES: upsert po id_czynnosci + zachowanie zamkniętych."""
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.processors.data_source import DataFrameDataSource
from src.processors.mes_processor import MESProcessor, get_product_profile


def _build_df(rows: list) -> pd.DataFrame:
    """Buduje DataFrame w kształcie zgodnym z widokiem ERP."""
    return pd.DataFrame(rows)


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "test_inc.sqlite"


def _row(id_czynnosci, produkt, proces, czas, status="zamknięte", zp="ZP1", zs="ZS1"):
    return {
        "IdCzynnosci": id_czynnosci,
        "ProduktKod": produkt,
        "ProcesKod": proces,
        "ProcesNazwa": proces.title(),
        "ProduktNazwa": f"Wyrób {produkt}",
        "CzasRealizacjiSztuka": czas,
        "PZL_Status": status,
        "ZP": zp,
        "ZS": zs,
        "DziałZP": "KiT",
        "SztukWyrobu": 10,
    }


def test_first_run_auto_picks_full(tmp_db):
    """Pusta baza → tryb 'auto' wybiera 'full'."""
    df = _build_df([
        _row(1, "029-0001-001", "KROJENIE", 2.0),
        _row(2, "029-0001-001", "ZGRZEWANIE", 10.0),
    ])
    proc = MESProcessor(data_source=DataFrameDataSource(df), db_path=tmp_db)
    assert proc.has_existing_data() is False

    count = proc.process_and_save(mode="auto")
    assert count == 1
    assert proc.has_existing_data() is True


def test_incremental_upserts_new_and_modified(tmp_db):
    """Upsert: nowy rekord dodany, zmodyfikowany nadpisany (id_czynnosci jako klucz)."""
    df_full = _build_df([
        _row(1, "029-0001-001", "KROJENIE", 2.0),
        _row(2, "029-0001-001", "KROJENIE", 4.0),
    ])
    MESProcessor(data_source=DataFrameDataSource(df_full), db_path=tmp_db).process_and_save(mode="full")

    # Incremental: modyfikacja rekordu #2 (czas 4.0 → 6.0) + nowy rekord #3
    df_inc = _build_df([
        _row(2, "029-0001-001", "KROJENIE", 6.0),
        _row(3, "029-0001-001", "KROJENIE", 8.0),
    ])
    proc2 = MESProcessor(data_source=DataFrameDataSource(df_inc), db_path=tmp_db)
    proc2.process_and_save(mode="incremental")

    # Raw ops: 3 rekordy (nie ma duplikatów)
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), MIN(real_time_per_unit_min), MAX(real_time_per_unit_min) FROM mes_raw_operations;")
    count, minimum, maximum = cur.fetchone()
    conn.close()
    assert count == 3
    assert minimum == 2.0
    assert maximum == 8.0

    # Statystyki: mediana z [2, 6, 8] = 6.0
    profile = get_product_profile("029-0001-001", db_path=tmp_db)
    krojenie = profile.processes["KROJENIE"]
    assert krojenie.median_time_per_unit_min == 6.0
    assert krojenie.sample_count == 3


def test_incremental_reaggregates_only_touched_products(tmp_db):
    """Drugi produkt nie jest ruszany przy upsercie tylko pierwszego."""
    df_full = _build_df([
        _row(1, "029-0001-001", "KROJENIE", 2.0),
        _row(2, "030-0001-001", "KROJENIE", 100.0),
    ])
    MESProcessor(data_source=DataFrameDataSource(df_full), db_path=tmp_db).process_and_save(mode="full")

    # Incremental — tylko pierwszy produkt
    df_inc = _build_df([_row(3, "029-0001-001", "KROJENIE", 4.0)])
    MESProcessor(data_source=DataFrameDataSource(df_inc), db_path=tmp_db).process_and_save(mode="incremental")

    # Drugi produkt nietknięty: mediana wciąż 100.0
    profile2 = get_product_profile("030-0001-001", db_path=tmp_db)
    assert profile2.processes["KROJENIE"].median_time_per_unit_min == 100.0
    assert profile2.processes["KROJENIE"].sample_count == 1

    # Pierwszy produkt zaktualizowany: mediana z [2, 4] = 3.0
    profile1 = get_product_profile("029-0001-001", db_path=tmp_db)
    assert profile1.processes["KROJENIE"].median_time_per_unit_min == 3.0
    assert profile1.processes["KROJENIE"].sample_count == 2


def test_incremental_refresh_metadata_written(tmp_db):
    """Po każdym zapisie app_metadata ma komplet kluczy."""
    from src.db_metadata import get_refresh_info

    df = _build_df([_row(1, "029-0001-001", "KROJENIE", 2.0)])
    MESProcessor(data_source=DataFrameDataSource(df), db_path=tmp_db).process_and_save(mode="full")

    info = get_refresh_info(db_path=tmp_db)
    assert info["last_refresh_at"] is not None
    assert info["last_refresh_mode"] == "full"
    assert info["last_refresh_rows"] == "1"


def test_incremental_when_schema_is_old_falls_back(tmp_db):
    """Stary schemat raw ops (bez id_czynnosci) → has_existing_data False → tryb 'auto' wybiera 'full'."""
    # Budujemy "starą" bazę ręcznie
    conn = sqlite3.connect(tmp_db)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE mes_raw_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT,
            process_code TEXT,
            process_name TEXT,
            product_name TEXT,
            client_code TEXT,
            dzial_zp TEXT,
            zp_number TEXT,
            zs_number TEXT,
            real_time_per_unit_min REAL,
            unit_count INTEGER,
            planned_time_total_min REAL,
            planned_time_per_unit_min REAL,
            norm_time_total_min REAL,
            norm_time_per_unit_min REAL
        );
    """)
    cur.execute("INSERT INTO mes_raw_operations (product_code, process_code, process_name, real_time_per_unit_min) VALUES ('029-0001-001', 'KROJENIE', 'Krojenie', 5.0);")
    conn.commit()
    conn.close()

    proc = MESProcessor(data_source=DataFrameDataSource(_build_df([_row(1, "029-0001-001", "KROJENIE", 2.0)])), db_path=tmp_db)
    # Stary schemat → False
    assert proc.has_existing_data() is False
    # 'auto' → 'full' → przebudowa
    proc.process_and_save(mode="auto")
    # Teraz już jest nowy schemat
    assert proc.has_existing_data() is True