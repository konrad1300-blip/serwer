"""Testy jednostkowe dla procesora bazy MES (nowa wersja: CSV-first)."""
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.processors.data_source import DataFrameDataSource
from src.processors.mes_processor import (
    MESProcessor,
    get_all_product_profiles,
    get_product_profile,
    get_raw_operations,
)


@pytest.fixture
def temp_mes_dataframe():
    """Buduje DataFrame z surowymi danymi MES w formacie odpowiadającym CSV z ERP."""
    data = {
        "ProduktKod": [
            "029-0421-018", "029-0421-018",
            "029-0421-018", "029-0421-018", "029-0421-018",
            "030-1119-001", "030-1119-001",
            "INVALID_ROW", "030-1119-001",
        ],
        "ProcesKod": [
            "KROJENIE", "KROJENIE",
            "ZGRZEWANIE HF (MAŁY)", "PAKOWANIE", "KONTROLA",
            "KROJENIE", "ZGRZEWANIE HF (MAŁY)",
            "KROJENIE", "ZGRZEWANIE HF (MAŁY)",
        ],
        "ProcesNazwa": [
            "Krojenie", "Krojenie",
            "Zgrzewanie HF (Mały)", "Pakowanie", "Kontrola",
            "Krojenie", "Zgrzewanie HF (Mały)",
            "Krojenie", "Zgrzewanie HF (Mały)",
        ],
        "ProduktNazwa": [
            "Alubag Test 1", "Alubag Test 1",
            "Alubag Test 1", "Alubag Test 1", "Alubag Test 1",
            "Plandeka Test 2", "Plandeka Test 2",
            "Niepoprawny", "Plandeka Test 2",
        ],
        "CzasRealizacjiSztuka": [
            2.0, 4.0,
            10.0, 1.5, 1.0,
            5.0, 12.0,
            -5.0, None,
        ],
        "SztukWyrobu": [10, 10, 10, 10, 10, 5, 5, 1, 5],
        "ZP": ["ZP001", "ZP002", "ZP001", "ZP001", "ZP001", "ZP003", "ZP003", "ZP999", "ZP003"],
        "ZS": ["ZS001", "ZS002", "ZS001", "ZS001", "ZS001", "ZS003", "ZS003", "ZS999", "ZS003"],
        "DziałZP": ["KiT", "T4", "KiT", "KiT", "KiT", "T4", "T4", "T4", "T4"],
        "CzasPlanowany[min]": [20.0, 25.0, 30.0, 15.0, 12.0, 40.0, 60.0, 0.0, 40.0],
        "CzasPlanowanySztuka[min]": [2.0, 2.5, 3.0, 1.5, 1.2, 8.0, 12.0, 0.0, 8.0],
        "CzasNormatywny[min]": [18.0, 22.0, 28.0, 14.0, 11.0, 38.0, 55.0, 0.0, 38.0],
        "CzasNormatywnySztuka": [1.8, 2.2, 2.8, 1.4, 1.1, 7.6, 11.0, 0.0, 7.6],
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_db_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "test_baza.sqlite"


def test_mes_processing_and_db_creation(temp_mes_dataframe, temp_db_path):
    ds = DataFrameDataSource(temp_mes_dataframe, label="Test DataFrame")
    processor = MESProcessor(data_source=ds, db_path=temp_db_path)
    count = processor.process_and_save()

    assert count == 2  # 029-0421-018, 030-1119-001
    assert temp_db_path.exists()

    profile = get_product_profile("029-0421-018", db_path=temp_db_path)
    assert profile is not None
    assert profile.client_code == "029"
    assert "KROJENIE" in profile.processes
    assert "ZGRZEWANIE HF (MAŁY)" in profile.processes

    krojenie = profile.processes["KROJENIE"]
    # median z [2.0, 4.0] = 3.0
    assert krojenie.median_time_per_unit_min == 3.0
    assert krojenie.q25_time_per_unit_min == 2.5
    assert krojenie.q50_time_per_unit_min == 3.0
    assert krojenie.q75_time_per_unit_min == 3.5

    zgrzewanie = profile.processes["ZGRZEWANIE HF (MAŁY)"]
    assert zgrzewanie.median_time_per_unit_min == 10.0


def test_get_all_product_profiles(temp_mes_dataframe, temp_db_path):
    ds = DataFrameDataSource(temp_mes_dataframe)
    MESProcessor(data_source=ds, db_path=temp_db_path).process_and_save()

    profiles = get_all_product_profiles(db_path=temp_db_path)
    assert len(profiles) == 2
    codes = {p.product_code for p in profiles}
    assert "029-0421-018" in codes
    assert "030-1119-001" in codes


def test_nonexistent_product(temp_db_path):
    profile = get_product_profile("NIE_ISTNIEJE", db_path=temp_db_path)
    assert profile is None


def test_raw_operations_table(temp_mes_dataframe, temp_db_path):
    """Sprawdzenie, czy raw ops zawiera Dział ZP, ZP, ZS, plan i normy."""
    ds = DataFrameDataSource(temp_mes_dataframe)
    MESProcessor(data_source=ds, db_path=temp_db_path).process_and_save()

    conn = sqlite3.connect(temp_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mes_raw_operations;")
    total = c.fetchone()[0]
    c.execute("""
        SELECT dzial_zp, zp_number, zs_number, planned_time_per_unit_min,
               planned_time_total_min, norm_time_per_unit_min, norm_time_total_min
        FROM mes_raw_operations
        WHERE product_code = '029-0421-018' AND process_code = 'KROJENIE'
        ORDER BY zp_number LIMIT 1;
    """)
    row = c.fetchone()
    conn.close()

    assert total > 0
    assert row is not None
    dzial_zp, zp, zs, planned_unit, planned_total, norm_unit, norm_total = row
    assert dzial_zp == "KiT"
    assert zp == "ZP001"
    assert zs == "ZS001"
    assert planned_unit == 2.0
    assert planned_total == 20.0
    assert norm_unit == 1.8
    assert norm_total == 18.0


def test_raw_operations_reader(temp_mes_dataframe, temp_db_path):
    """Test funkcji get_raw_operations — zwraca listę RawOperation z działem ZP."""
    ds = DataFrameDataSource(temp_mes_dataframe)
    MESProcessor(data_source=ds, db_path=temp_db_path).process_and_save()

    ops = get_raw_operations("029-0421-018", "KROJENIE", db_path=temp_db_path)
    assert len(ops) == 2
    # Sortowanie: dzial_zp, zp_number, zs_number → KiT przed T4.
    assert ops[0].dzial_zp == "KiT"
    assert ops[1].dzial_zp == "T4"
    assert ops[0].zp_number == "ZP001"
    assert ops[0].zs_number == "ZS001"
    assert ops[0].planned_time_per_unit_min == 2.0
    assert ops[0].norm_time_total_min == 18.0