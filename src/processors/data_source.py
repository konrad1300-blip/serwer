"""Abstrakcja źródeł danych MES (Procesor 0).

Umożliwia jednolite wczytywanie danych z różnych źródeł:
- plik CSV (produkcja, domyślnie),
- plik Excel (fallback, kompatybilność wsteczna),
- DataFrame w pamięci (upload z UI, testy),
- ERP XL (SQL Server — pełny pull lub przyrostowy).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Union

import pandas as pd

from src.config import (
    ERP_BOM_VIEW,
    ERP_CONNECTION_TIMEOUT,
    ERP_DATABASE,
    ERP_DRIVER,
    ERP_PWD,
    ERP_SERVER,
    ERP_UID,
    ERP_VIEW,
    INCREMENTAL_LOOKBACK_DAYS,
)


class DataSource(ABC):
    """Interfejs źródła danych MES."""

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Zwraca surowy DataFrame z danymi MES."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Krótka etykieta źródła (do logu i UI)."""
        ...


class CSVDataSource(DataSource):
    """
    Źródło: plik CSV z PRZECINKIEM jako separatorem dziesiętnym
    (standard eksportu z ERP XL).

    Separator pól:
    - `separator=None` (domyślnie) — auto-detekcja na podstawie pierwszej linii
      pliku. Obsługiwane: `,`, `;`, tabulator, `|`.
    - `separator=","` / `";"` / itd. — wymuszenie konkretnego znaku.

    Kodowanie:
    - domyślnie `utf-8-sig` — toleruje BOM.
    - w razie `UnicodeDecodeError` automatyczny fallback na CP1250.
    """

    def __init__(
        self,
        path: Union[str, Path],
        separator: Optional[str] = None,
        decimal: str = ",",
        encoding: str = "utf-8-sig",
    ):
        self.path = Path(path)
        self.separator = separator
        self.decimal = decimal
        self.encoding = encoding

    @property
    def name(self) -> str:
        return f"CSV: {self.path.name}"

    def _candidate_encodings(self) -> list:
        encs = [self.encoding]
        if self.encoding.lower() not in ("cp1250", "cp1252"):
            encs.append("cp1250")
        return encs

    def _detect_separator(self) -> str:
        for enc in self._candidate_encodings():
            try:
                with open(self.path, "r", encoding=enc, newline="") as f:
                    first_line = f.readline()
            except (UnicodeDecodeError, OSError):
                continue

            candidates = [",", ";", "\t", "|"]
            counts = {sep: first_line.count(sep) for sep in candidates}
            best = max(counts, key=counts.get)
            if counts[best] > 0:
                return best
            return ","
        return ","

    def _read(self, sep: str, encoding: str) -> pd.DataFrame:
        return pd.read_csv(
            self.path,
            sep=sep,
            decimal=self.decimal,
            quotechar='"',
            encoding=encoding,
        )

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Nie znaleziono pliku CSV: {self.path}")

        sep = self.separator or self._detect_separator()

        last_error: Optional[Exception] = None
        for enc in self._candidate_encodings():
            try:
                return self._read(sep, enc)
            except UnicodeDecodeError as ex:
                last_error = ex
                continue

        raise UnicodeDecodeError(
            last_error.encoding, last_error.object, last_error.start,
            last_error.end, f"Nie udało się wczytać pliku {self.path} w żadnym z kodowań: "
                            f"{self._candidate_encodings()}"
        )


class ExcelDataSource(DataSource):
    """Źródło: plik XLSX (kompatybilność wsteczna)."""

    def __init__(self, path: Union[str, Path], sheet_name: Union[int, str] = 0):
        self.path = Path(path)
        self.sheet_name = sheet_name

    @property
    def name(self) -> str:
        return f"Excel: {self.path.name}"

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Nie znaleziono pliku Excel: {self.path}")
        return pd.read_excel(self.path, sheet_name=self.sheet_name)


class DataFrameDataSource(DataSource):
    """Źródło: DataFrame w pamięci (upload z UI, testy jednostkowe)."""

    def __init__(self, df: pd.DataFrame, label: str = "DataFrame (in-memory)"):
        self.df = df
        self._label = label

    @property
    def name(self) -> str:
        return self._label

    def load(self) -> pd.DataFrame:
        return self.df.copy()


class ERPDataSource(DataSource):
    """
    Źródło: bezpośrednie zapytanie do widoku ERP XL (SQL Server) przez pyodbc.

    Tryby pracy:
    - `load(mode="full")` — pobiera cały widok (pierwsze uruchomienie, przebudowa).
    - `load(mode="incremental", lookback_days=90)` — pobiera wyłącznie rekordy
      z ostatnich N dni LUB o statusie innym niż 'zamknięte'. Zamknięte rekordy
      starsze niż N dni są pomijane (są niezmienne — zasada biznesowa).

    Poświadczenia pobierane z `.env` przez `src.config`. W razie braku — czytelny błąd.
    """

    def __init__(
        self,
        view: Optional[str] = None,
        connection_timeout: Optional[int] = None,
    ):
        self.view = view or ERP_VIEW
        self.timeout = connection_timeout or ERP_CONNECTION_TIMEOUT

    @property
    def name(self) -> str:
        return f"ERP XL: {ERP_SERVER}/{ERP_DATABASE}::{self.view}"

    def _build_conn_str(self) -> str:
        """Składa connection string dla pyodbc na podstawie konfiguracji."""
        return (
            f"DRIVER={{{ERP_DRIVER}}};"
            f"SERVER={ERP_SERVER};"
            f"DATABASE={ERP_DATABASE};"
            f"UID={ERP_UID};"
            f"PWD={ERP_PWD};"
            f"Connection Timeout={self.timeout};"
        )

    def _connect(self):
        """
        Otwiera połączenie z ERP XL. Rzuca ImportError (brak pyodbc)
        lub ValueError (brak poświadczeń w .env) z czytelnym komunikatem.
        """
        try:
            import pyodbc
        except ImportError as ex:
            raise ImportError(
                "Biblioteka 'pyodbc' nie jest zainstalowana. "
                "Zainstaluj: `pip install pyodbc` (wymaga sterownika ODBC dla SQL Server)."
            ) from ex

        if not ERP_UID or not ERP_PWD:
            raise ValueError(
                "Brak poświadczeń ERP. Skopiuj `.env.example` → `.env` w katalogu "
                "głównym projektu i uzupełnij `ERP_UID` oraz `ERP_PWD`."
            )

        return pyodbc.connect(self._build_conn_str(), timeout=self.timeout)

    def load(
        self,
        mode: str = "full",
        lookback_days: int = INCREMENTAL_LOOKBACK_DAYS,
    ) -> pd.DataFrame:
        """
        Pobiera dane z widoku ERP.

        :param mode: 'full' — pełny pull; 'incremental' — tylko nowe/nie-zamknięte.
        :param lookback_days: szerokość okna czasowego dla trybu przyrostowego.
        :return: surowy DataFrame z widoku.
        """
        if mode == "full":
            query = f"SELECT * FROM [dbo].[{self.view}];"
            params: list = []
        elif mode == "incremental":
            # ISNULL — włącza rekordy z NULL-owym statusem (jeszcze nie zamknięte).
            query = (
                f"SELECT * FROM [dbo].[{self.view}] "
                f"WHERE DataWysylki >= DATEADD(day, -?, GETDATE()) "
                f"   OR ISNULL(PZL_Status, '') <> 'zamknięte';"
            )
            params = [lookback_days]
        else:
            raise ValueError(f"Nieznany tryb pobierania: {mode!r}. Dozwolone: 'full', 'incremental'.")

        with self._connect() as conn:
            df = pd.read_sql(query, conn, params=params)
        return df

    def test_connection(self) -> Tuple[bool, str]:
        """
        Testuje połączenie i dostępność widoku. Zwraca (sukces, komunikat).
        Nie rzuca wyjątków — wszystko zamieniane na krotkę, żeby UI mógł
        bezpiecznie wyświetlić komunikat.
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT TOP 1 * FROM [dbo].[{self.view}];")
                cur.fetchone()
            return True, f"Połączenie OK — {ERP_SERVER}/{ERP_DATABASE} (widok: {self.view})"
        except ImportError as ex:
            return False, f"Brak biblioteki pyodbc: {ex}"
        except ValueError as ex:
            return False, f"Brak poświadczeń: {ex}"
        except Exception as ex:
            return False, f"Błąd połączenia: {ex}"


class BOMDataSource(ERPDataSource):
    """
    Źródło danych BOM z widoku ERP XL (`_im_mm_kalkulacja_Excel`).

    Dziedziczy po `ERPDataSource` (wspólne poświadczenia, sterownik, serwer,
    baza). Różni się tylko nazwą widoku i brakiem trybu przyrostowego —
    widok BOM nie posiada pola statusu ani daty wysyłki, więc `load()`
    zawsze wykonuje pełny pull.
    """

    def __init__(
        self,
        view: Optional[str] = None,
        connection_timeout: Optional[int] = None,
    ):
        super().__init__(
            view=view or ERP_BOM_VIEW,
            connection_timeout=connection_timeout,
        )

    @property
    def name(self) -> str:
        return f"BOM ERP: {ERP_SERVER}/{ERP_DATABASE}::{self.view}"

    def load(self, mode: str = "full", lookback_days: int = 0) -> pd.DataFrame:
        """BOM zawsze w trybie pełnym (brak znacznika przyrostowego w widoku)."""
        return super().load(mode="full")