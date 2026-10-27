"""Testy jednostkowe dla abstrakcji źródeł danych MES.

Sprawdzają:
- auto-detekcję separatora (`,` / `;` / tab / `|`),
- tolerancję BOM w UTF-8 (eksport LibreOffice / Excel),
- fallback kodowania UTF-8 → CP1250 (starsze eksporty Windows),
- kontrakt `DataFrameDataSource` (kopia, nie referencja),
- zachowanie na brakującym pliku.
"""
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.processors.data_source import (
    CSVDataSource,
    DataFrameDataSource,
    ExcelDataSource,
)


# --- Fixtures: pliki CSV w różnych wariantach ---

@pytest.fixture
def csv_comma():
    """CSV z przecinkiem jako separatorem, UTF-8 bez BOM."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("ProduktKod,ProcesKod,CzasRealizacjiSztuka\n")
        f.write("029-0001-001,KROJENIE,2.5\n")
        f.write("029-0001-001,ZGRZEWANIE,10.0\n")
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def csv_semicolon():
    """CSV ze średnikiem jako separatorem, UTF-8 — wariant HansAA (25 kolumn)."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("DziałZP;ProduktKod;ProcesKod;CzasRealizacjiSztuka\n")
        f.write("KiT;029-0001-001;KROJENIE;2,5\n")
        f.write("T4;029-0001-001;ZGRZEWANIE;10,0\n")
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def csv_tab():
    """CSV z tabulatorem jako separatorem."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write("ProduktKod\tProcesKod\tCzasRealizacjiSztuka\n")
        f.write("029-0001-001\tKROJENIE\t2.5\n")
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def csv_with_bom():
    """CSV z BOM-em na początku — typowy artefakt LibreOffice / Excel."""
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write("\ufeffProduktKod;ProcesKod;CzasRealizacjiSztuka\n".encode("utf-8"))
        f.write("029-0001-001;KROJENIE;2,5\n".encode("utf-8"))
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def csv_cp1250():
    """CSV w kodowaniu CP1250 z polskimi znakami — starsze eksporty Windows."""
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write("DziałZP;ProduktKod;ProcesKod;CzasRealizacjiSztuka\n".encode("cp1250"))
        f.write("KiT;029-0001-001;KROJENIE;2,5\n".encode("cp1250"))
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


# --- Testy auto-detekcji separatora ---

def test_autodetect_comma(csv_comma):
    ds = CSVDataSource(csv_comma)
    df = ds.load()
    assert list(df.columns) == ["ProduktKod", "ProcesKod", "CzasRealizacjiSztuka"]
    assert len(df) == 2


def test_autodetect_semicolon(csv_semicolon):
    ds = CSVDataSource(csv_semicolon)
    df = ds.load()
    assert "DziałZP" in df.columns
    assert "ProduktKod" in df.columns
    assert "CzasRealizacjiSztuka" in df.columns
    assert len(df) == 2


def test_autodetect_tab(csv_tab):
    ds = CSVDataSource(csv_tab)
    df = ds.load()
    assert "ProduktKod" in df.columns
    assert len(df) == 1


def test_explicit_separator_overrides_detection(csv_semicolon):
    """Gdy użytkownik poda separator jawnie, auto-detekcja nie wchodzi w grę."""
    ds = CSVDataSource(csv_semicolon, separator=";")
    df = ds.load()
    assert "ProduktKod" in df.columns


# --- Testy BOM ---

def test_bom_stripped_from_first_column(csv_with_bom):
    """Bez utf-8-sig pierwsza kolumna byłaby '\\ufeffProduktKod'."""
    ds = CSVDataSource(csv_with_bom)
    df = ds.load()
    assert df.columns[0] == "ProduktKod"
    assert "\ufeff" not in df.columns[0]


# --- Testy kodowania ---

def test_cp1250_fallback(csv_cp1250):
    """Plik CP1250 — utf-8-sig zawiedzie, musi być automatyczny fallback na cp1250."""
    ds = CSVDataSource(csv_cp1250)  # domyślnie encoding="utf-8-sig"
    df = ds.load()
    assert df.columns[0] == "DziałZP"
    assert "ProduktKod" in df.columns


# --- Testy obsługi błędów ---

def test_nonexistent_file():
    ds = CSVDataSource("/nie/istnieje/plik.csv")
    with pytest.raises(FileNotFoundError):
        ds.load()


# --- Testy pozostałych źródeł ---

def test_dataframe_source_returns_copy():
    """DataFrameDataSource.load() zwraca kopię, nie referencję."""
    df_in = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
    ds = DataFrameDataSource(df_in, label="test-label")
    assert ds.name == "test-label"

    df_out = ds.load()
    pd.testing.assert_frame_equal(df_in, df_out)

    # Mutacja kopii nie wpływa na oryginał.
    df_out.loc[0, "A"] = 999
    assert df_in.loc[0, "A"] == 1


def test_excel_nonexistent():
    ds = ExcelDataSource("/nie/istnieje/plik.xlsx")
    with pytest.raises(FileNotFoundError):
        ds.load()