"""Testy jednostkowe dla ERPDataSource (mock pyodbc — bez realnego SQL Server).

Uwaga o mockowaniu pyodbc:
`data_source.py` importuje `pyodbc` **lokalnie** wewnątrz `ERPDataSource._connect()`
— zabieg celowy, żeby moduł dał się zaimportować w środowiskach bez pyodbc
(tryb CSV / DataFrame). Dlatego mockujemy przez podmianę w `sys.modules`,
a nie przez `patch("src.processors.data_source.pyodbc")` — ten atrybut nie istnieje.
"""
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.processors.data_source import ERPDataSource


@pytest.fixture(autouse=True)
def _set_erp_credentials(monkeypatch):
    """Wstrzykuje testowe poświadczenia do modułu data_source (unikamy .env w testach)."""
    import src.processors.data_source as ds_mod
    monkeypatch.setattr(ds_mod, "ERP_UID", "test_user")
    monkeypatch.setattr(ds_mod, "ERP_PWD", "test_pwd")


def _mock_pyodbc_module() -> MagicMock:
    """
    Buduje mock modułu pyodbc z gotowym kontekstem menedżera połączenia.

    Zwraca obiekt, który można wstawić do `sys.modules["pyodbc"]`. Jego
    `connect()` zwraca connection-mock obsługujący `with ... as conn`.
    """
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_pyodbc = MagicMock()
    mock_pyodbc.connect.return_value = mock_conn
    return mock_pyodbc


def test_load_full_uses_select_star():
    """Tryb 'full' wysyła SELECT * bez filtra WHERE."""
    mock_pyodbc = _mock_pyodbc_module()

    with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}), \
         patch("src.processors.data_source.pd.read_sql") as mock_read:
        mock_read.return_value = pd.DataFrame({"ProduktKod": ["029-0001-001"]})

        erp = ERPDataSource()
        df = erp.load(mode="full")

        assert len(df) == 1
        called_sql = mock_read.call_args[0][0]
        assert "SELECT *" in called_sql
        assert "WHERE" not in called_sql


def test_load_incremental_uses_where_clause():
    """Tryb 'incremental' zawiera filtr czasu i statusu, parametr = lookback_days."""
    mock_pyodbc = _mock_pyodbc_module()

    with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}), \
         patch("src.processors.data_source.pd.read_sql") as mock_read:
        mock_read.return_value = pd.DataFrame()

        erp = ERPDataSource()
        erp.load(mode="incremental", lookback_days=90)

        called_sql = mock_read.call_args[0][0]
        called_params = mock_read.call_args[1].get("params", [])
        assert "WHERE" in called_sql
        assert "DataWysylki" in called_sql
        assert "PZL_Status" in called_sql
        assert called_params == [90]


def test_load_unknown_mode_raises():
    erp = ERPDataSource()
    with pytest.raises(ValueError):
        erp.load(mode="bogus")


def test_missing_credentials_raises(monkeypatch):
    """Brak UID/hasła → ValueError z czytelnym komunikatem."""
    import src.processors.data_source as ds_mod
    monkeypatch.setattr(ds_mod, "ERP_UID", "")
    monkeypatch.setattr(ds_mod, "ERP_PWD", "")

    erp = ERPDataSource()
    with pytest.raises(ValueError, match="Brak poświadczeń"):
        erp._connect()


def test_test_connection_success():
    mock_pyodbc = _mock_pyodbc_module()

    with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
        erp = ERPDataSource()
        ok, msg = erp.test_connection()

        assert ok is True
        assert "Połączenie OK" in msg


def test_test_connection_failure_returns_false():
    mock_pyodbc = MagicMock()
    mock_pyodbc.connect.side_effect = Exception("Timeout")

    with patch.dict(sys.modules, {"pyodbc": mock_pyodbc}):
        erp = ERPDataSource()
        ok, msg = erp.test_connection()

        assert ok is False
        assert "Timeout" in msg