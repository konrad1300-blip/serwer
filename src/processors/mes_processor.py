"""Moduł przetwarzania danych historycznych MES (Procesor 1).

Obsługuje wczytywanie z różnych źródeł (CSV, XLSX, DataFrame, ERP XL)
poprzez abstrakcję DataSource. Zapis do SQLite odbywa się w jednym z trybów:

- 'full'        — DROP + CREATE wszystkich tabel, pełna agregacja.
- 'incremental' — UPSERT raw ops po `id_czynnosci`, reagregacja statystyk
                  wyłącznie dla produktów, których rekordy uległy zmianie.
- 'auto'        — wybiera 'incremental' jeśli baza ma poprawny schemat i dane,
                  w przeciwnym wypadku 'full'.

Reguła biznesowa przyrostowego pullu: rekordy PZL_Status='zamknięte' starsze
niż okno INCREMENTAL_LOOKBACK_DAYS są pomijane (są niezmienne). Rekordy
z ostatnich N dni LUB o innym statusie są zawsze pobierane ponownie.
"""
import argparse
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple, Union

import pandas as pd

from src.config import (
    DB_PATH,
    MAX_TIME_PER_UNIT_MIN,
    MIN_TIME_PER_UNIT_MIN,
    PROCESSED_DATA_DIR,
    RAW_DATA_PATH,
    find_raw_data_file,
)
from src.db_metadata import set_refresh_info
from src.models import ProcessTimeStat, ProductProfile, RawOperation
from src.processors.data_source import (
    CSVDataSource,
    DataSource,
    ExcelDataSource,
)


# Kolumny wymagane (podstawowe identyfikatory i realny czas).
REQUIRED_MES_COLUMNS = {
    "ProduktKod",
    "ProcesKod",
    "ProcesNazwa",
    "ProduktNazwa",
    "CzasRealizacjiSztuka",
}

# Kolumny nowego schematu raw ops (klucz + status + znacznik czasu).
RAW_OPS_SCHEMA_COLUMNS = {"id_czynnosci", "pzl_status", "fetched_at"}

# SQL: pełne wstawienie/upsert raw op (17 pól).
_RAW_OPS_INSERT_SQL = """
    INSERT OR REPLACE INTO mes_raw_operations (
        id_czynnosci, product_code, process_code, process_name, product_name,
        client_code, dzial_zp, zp_number, zs_number, real_time_per_unit_min,
        unit_count, planned_time_total_min, planned_time_per_unit_min,
        norm_time_total_min, norm_time_per_unit_min, pzl_status, fetched_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# Regex na końcową postać znormalizowanej nazwy — tylko [a-z0-9].
_ALNUM_RE = re.compile(r"[^a-z0-9]")

# Transliteracja polskich znaków + warianty z błędnego dekodowania CP1250 jako
# CP1252/latin-1 (typowy efekt czytania polskiego CSV w złym kodowaniu).
_PL_TRANSLITERACJA = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "³": "l", "¹": "a", "ê": "e", "ñ": "n", "æ": "c", "¿": "z", "Ÿ": "z",
})


def _normalize(name: str) -> str:
    """
    Normalizuje nazwę kolumny do postaci [a-z0-9]:
    - małe litery,
    - ręczna transliteracja polskich znaków (UTF-8 i CP1250-as-CP1252),
    - NFKD + ASCII-only (usuwa resztki akcentów spoza mapy),
    - usunięcie wszystkiego poza [a-z0-9].
    """
    s = str(name).lower().translate(_PL_TRANSLITERACJA)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _ALNUM_RE.sub("", s)


def _find_column(
    df_columns,
    keywords: List[str],
    exclude: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Znajduje kolumnę zawierającą wszystkie słowa kluczowe (case-insensitive,
    ignorując spacje/nawiasy/podkreślenia i polskie znaki diakrytyczne) i NIE
    zawierającą żadnego ze słów `exclude`.
    """
    exclude = exclude or []
    for col in df_columns:
        normalized = _normalize(col)
        if all(_normalize(kw) in normalized for kw in keywords):
            if any(_normalize(kw) in normalized for kw in exclude):
                continue
            return col
    return None


def _build_default_data_source() -> DataSource:
    """
    Buduje domyślne źródło danych: auto-detect wg RAW_DATA_FILENAMES.
    Rzuca FileNotFoundError, jeśli nic nie znajdzie.
    """
    raw_path = find_raw_data_file()
    if raw_path is None:
        raw_path = RAW_DATA_PATH

    if not Path(raw_path).exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku źródłowego MES. Szukano: {raw_path}. "
            f"Umieść plik 'HansAA_AI_KiT_v8_9_PRODvsKiT.csv' w katalogu data/raw/."
        )

    suffix = Path(raw_path).suffix.lower()
    if suffix == ".csv":
        return CSVDataSource(raw_path, separator=None, decimal=",")
    elif suffix in (".xlsx", ".xls"):
        return ExcelDataSource(raw_path)
    else:
        raise ValueError(f"Nieobsługiwany format pliku źródłowego: {suffix}")


def _aggregate_process_stats(
    df_clean: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Agreguje surowe operacje do statystyk procesowych (mediany + percentyle)
    oraz profilów produktowych. Zwraca krotkę (stats_df, profiles_df).
    """
    def q25(x): return x.quantile(0.25)
    def q50(x): return x.quantile(0.50)
    def q75(x): return x.quantile(0.75)

    grouped = df_clean.groupby(["ProduktKod", "ProcesKod"]).agg(
        median_time=("CzasRealizacjiSztuka", "median"),
        q25_time=("CzasRealizacjiSztuka", q25),
        q50_time=("CzasRealizacjiSztuka", q50),
        q75_time=("CzasRealizacjiSztuka", q75),
        min_time=("CzasRealizacjiSztuka", "min"),
        max_time=("CzasRealizacjiSztuka", "max"),
        sample_count=("CzasRealizacjiSztuka", "count"),
        proces_nazwa=("ProcesNazwa", "first"),
        produkt_nazwa=("ProduktNazwa", "first"),
        klient_kod=("KlientKod", "first"),
    ).reset_index()

    prod_grouped = grouped.groupby("ProduktKod").agg(
        klient_kod=("klient_kod", "first"),
        produkt_nazwa=("produkt_nazwa", "first"),
        total_median_time=("median_time", "sum"),
        process_count=("ProcesKod", "count"),
        total_samples=("sample_count", "sum"),
    ).reset_index()

    return grouped, prod_grouped


class MESProcessor:
    """Wczytuje, czyści, agreguje dane MES i zapisuje je do bazy SQLite."""

    def __init__(
        self,
        data_source: Optional[DataSource] = None,
        db_path: Optional[Union[str, Path]] = None,
    ):
        self.data_source = data_source
        self.db_path = Path(db_path) if db_path else DB_PATH

    # ------------------------------------------------------------------
    # Wykrywanie stanu bazy
    # ------------------------------------------------------------------
    def _raw_table_has_current_schema(self, cursor: sqlite3.Cursor) -> bool:
        """True, jeśli mes_raw_operations istnieje i ma nowy schemat (klucz + status)."""
        try:
            cursor.execute("PRAGMA table_info(mes_raw_operations);")
            cols = {row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            return False
        return RAW_OPS_SCHEMA_COLUMNS.issubset(cols)

    def has_existing_data(self) -> bool:
        """
        True, jeśli baza istnieje, ma aktualny schemat raw ops i co najmniej
        jeden wiersz. Deterministyczne dla decyzji full/incremental.
        """
        if not self.db_path.exists():
            return False
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            if not self._raw_table_has_current_schema(cur):
                return False
            cur.execute("SELECT COUNT(*) FROM mes_raw_operations;")
            return cur.fetchone()[0] > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Wczytywanie i czyszczenie
    # ------------------------------------------------------------------
    def _load_data(self) -> pd.DataFrame:
        """Wczytuje DataFrame ze źródła i waliduje wymagane kolumny."""
        if self.data_source is None:
            self.data_source = _build_default_data_source()

        df = self.data_source.load()
        missing = REQUIRED_MES_COLUMNS - set(df.columns)
        if missing:
            found = sorted(df.columns.tolist())
            raise ValueError(
                f"Źródło '{self.data_source.name}' nie zawiera wymaganych kolumn: "
                f"{sorted(missing)}. Znalezione kolumny: {found}."
            )
        return df

    def _detect_optional_columns(self, df: pd.DataFrame) -> dict:
        """Wykrywa opcjonalne kolumny (fuzzy). Zwraca dict nazw źródłowych."""
        return {
            "planned_unit_col": _find_column(df.columns, ["planowany", "sztuka"]),
            "planned_total_col": _find_column(df.columns, ["planowany", "min"], exclude=["sztuka"]),
            "norm_unit_col": _find_column(df.columns, ["normatywny", "sztuka"]),
            "norm_total_col": _find_column(df.columns, ["normatywny", "min"], exclude=["sztuka"]),
            "zp_col": _find_column(df.columns, ["zp"], exclude=["dzial"]),
            "zs_col": _find_column(df.columns, ["zs"], exclude=["dzial"]),
            "dzial_zp_col": _find_column(df.columns, ["dzial"]),
            "unit_count_col": "SztukWyrobu" if "SztukWyrobu" in df.columns else None,
            "id_czynnosci_col": "IdCzynnosci" if "IdCzynnosci" in df.columns else None,
            "pzl_status_col": "PZL_Status" if "PZL_Status" in df.columns else None,
        }

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Czyści i normalizuje DataFrame. Dodaje kolumny: KlientKod, IdCzynnosci,
        PZL_Status. Filtruje wiersze z pustymi kodami i czasami poza zakresem.
        """
        df = df.copy()

        df["ProduktKod"] = df["ProduktKod"].astype(str).str.strip()
        df["ProcesKod"] = df["ProcesKod"].astype(str).str.strip().str.upper()
        df["ProcesNazwa"] = df["ProcesNazwa"].fillna(df["ProcesKod"]).astype(str).str.strip()
        df["ProduktNazwa"] = df["ProduktNazwa"].fillna("").astype(str).str.strip()

        # Czas — tolerancyjnie na przecinki (na wypadek CSV bez decimal=",").
        df["CzasRealizacjiSztuka"] = pd.to_numeric(
            df["CzasRealizacjiSztuka"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )

        # IdCzynnosci — klucz do upsert. Jeśli brak, syntetyzujemy z ZP+ZS+kodów.
        if "IdCzynnosci" in df.columns:
            df["IdCzynnosci"] = df["IdCzynnosci"].astype(str).str.strip()
        else:
            zp = df["ZP"].astype(str) if "ZP" in df.columns else ""
            zs = df["ZS"].astype(str) if "ZS" in df.columns else ""
            df["IdCzynnosci"] = (
                df["ProduktKod"].astype(str) + "|"
                + df["ProcesKod"].astype(str) + "|"
                + zp + "|" + zs
            )

        # PZL_Status — domyślnie 'zamknięte' (brak kolumny = brak przyrostowej selekcji).
        if "PZL_Status" in df.columns:
            df["PZL_Status"] = df["PZL_Status"].fillna("").astype(str).str.strip()
        else:
            df["PZL_Status"] = "zamknięte"

        valid_mask = (
            df["ProduktKod"].notna()
            & (df["ProduktKod"] != "")
            & (df["ProduktKod"] != "nan")
            & df["ProcesKod"].notna()
            & (df["ProcesKod"] != "")
            & (df["ProcesKod"] != "nan")
            & (df["IdCzynnosci"] != "")
            & (df["CzasRealizacjiSztuka"] >= MIN_TIME_PER_UNIT_MIN)
            & (df["CzasRealizacjiSztuka"] <= MAX_TIME_PER_UNIT_MIN)
        )
        df_clean = df[valid_mask].copy()
        df_clean["KlientKod"] = df_clean["ProduktKod"].str[:3]
        return df_clean

    # ------------------------------------------------------------------
    # Zapis — tryb pełny
    # ------------------------------------------------------------------
    def _create_schema(self, cursor: sqlite3.Cursor) -> None:
        """Tworzy od zera wszystkie tabele (DROP + CREATE)."""
        cursor.execute("DROP TABLE IF EXISTS mes_process_stats;")
        cursor.execute("""
            CREATE TABLE mes_process_stats (
                product_code TEXT NOT NULL,
                process_code TEXT NOT NULL,
                process_name TEXT NOT NULL,
                product_name TEXT,
                client_code TEXT NOT NULL,
                median_time_min REAL NOT NULL,
                q25_time_min REAL NOT NULL,
                q50_time_min REAL NOT NULL,
                q75_time_min REAL NOT NULL,
                min_time_min REAL NOT NULL,
                max_time_min REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                PRIMARY KEY (product_code, process_code)
            );
        """)

        cursor.execute("DROP TABLE IF EXISTS product_profiles;")
        cursor.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY,
                client_code TEXT NOT NULL,
                product_name TEXT,
                total_median_time_min REAL NOT NULL,
                process_count INTEGER NOT NULL,
                total_samples INTEGER NOT NULL
            );
        """)

        cursor.execute("DROP TABLE IF EXISTS mes_raw_operations;")
        cursor.execute("""
            CREATE TABLE mes_raw_operations (
                id_czynnosci TEXT PRIMARY KEY,
                product_code TEXT NOT NULL,
                process_code TEXT NOT NULL,
                process_name TEXT NOT NULL,
                product_name TEXT,
                client_code TEXT NOT NULL,
                dzial_zp TEXT,
                zp_number TEXT,
                zs_number TEXT,
                real_time_per_unit_min REAL NOT NULL,
                unit_count INTEGER,
                planned_time_total_min REAL,
                planned_time_per_unit_min REAL,
                norm_time_total_min REAL,
                norm_time_per_unit_min REAL,
                pzl_status TEXT NOT NULL DEFAULT 'zamknięte',
                fetched_at TEXT NOT NULL
            );
        """)

    def _write_raw_ops(
        self,
        cursor: sqlite3.Cursor,
        df_clean: pd.DataFrame,
        opt_cols: dict,
    ) -> int:
        """
        Wstawia/upsertuje surowe operacje. Zwraca liczbę wstawionych rekordów.
        """
        fetched_at = datetime.now().isoformat(timespec="seconds")

        def _val(row, col, kind="float"):
            if not col or col not in row or pd.isna(row[col]):
                return None
            try:
                return float(row[col]) if kind == "float" else int(row[col])
            except (ValueError, TypeError):
                return None

        def _str_or_empty(row, col):
            if not col or col not in row or pd.isna(row[col]):
                return ""
            return str(row[col]).strip()

        records = []
        for _, row in df_clean.iterrows():
            records.append((
                row["IdCzynnosci"],
                row["ProduktKod"],
                row["ProcesKod"],
                row["ProcesNazwa"],
                row["ProduktNazwa"],
                row["KlientKod"],
                _str_or_empty(row, opt_cols["dzial_zp_col"]),
                _str_or_empty(row, opt_cols["zp_col"]),
                _str_or_empty(row, opt_cols["zs_col"]),
                float(row["CzasRealizacjiSztuka"]),
                _val(row, opt_cols["unit_count_col"], "int"),
                _val(row, opt_cols["planned_total_col"], "float"),
                _val(row, opt_cols["planned_unit_col"], "float"),
                _val(row, opt_cols["norm_total_col"], "float"),
                _val(row, opt_cols["norm_unit_col"], "float"),
                row["PZL_Status"] or "zamknięte",
                fetched_at,
            ))

        cursor.executemany(_RAW_OPS_INSERT_SQL, records)
        return len(records)

    def _write_stats(
        self,
        cursor: sqlite3.Cursor,
        grouped: pd.DataFrame,
        prod_grouped: pd.DataFrame,
    ) -> None:
        """Wstawia statystyki procesowe i profile produktów."""
        stats_records = []
        for _, row in grouped.iterrows():
            stats_records.append((
                row["ProduktKod"], row["ProcesKod"], row["proces_nazwa"],
                row["produkt_nazwa"], row["klient_kod"],
                round(float(row["median_time"]), 4),
                round(float(row["q25_time"]), 4),
                round(float(row["q50_time"]), 4),
                round(float(row["q75_time"]), 4),
                round(float(row["min_time"]), 4),
                round(float(row["max_time"]), 4),
                int(row["sample_count"]),
            ))
        cursor.executemany(
            "INSERT OR REPLACE INTO mes_process_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            stats_records,
        )

        prod_records = []
        for _, row in prod_grouped.iterrows():
            prod_records.append((
                row["ProduktKod"], row["klient_kod"], row["produkt_nazwa"],
                round(float(row["total_median_time"]), 4),
                int(row["process_count"]),
                int(row["total_samples"]),
            ))
        cursor.executemany(
            "INSERT OR REPLACE INTO product_profiles VALUES (?, ?, ?, ?, ?, ?);",
            prod_records,
        )

    def _save_full(self, df_clean: pd.DataFrame, opt_cols: dict) -> Tuple[int, int]:
        """Tryb pełny: DROP + CREATE + pełna agregacja. Zwraca (products, rows)."""
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"💾 Zapis pełnej bazy do SQLite: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            self._create_schema(cursor)

            rows_written = self._write_raw_ops(cursor, df_clean, opt_cols)
            grouped, prod_grouped = _aggregate_process_stats(df_clean)
            self._write_stats(cursor, grouped, prod_grouped)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_prod ON mes_process_stats(product_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_client ON mes_process_stats(client_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_client ON product_profiles(client_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_prod_proc ON mes_raw_operations(product_code, process_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_zp ON mes_raw_operations(zp_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_zs ON mes_raw_operations(zs_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_dzial ON mes_raw_operations(dzial_zp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_status ON mes_raw_operations(pzl_status);")

            conn.commit()

            print(f"🎉 Baza utworzona pomyślnie!")
            print(f"   • Unikalnych produktów: {len(prod_grouped):,}")
            print(f"   • Unikalnych klientów: {prod_grouped['klient_kod'].nunique():,}")
            print(f"   • Zagregowanych procesów: {len(grouped):,}")
            print(f"   • Surowe odbicia operacji (raw ops): {rows_written:,}")

            return len(prod_grouped), rows_written
        finally:
            conn.close()

    def _save_incremental(self, df_clean: pd.DataFrame, opt_cols: dict) -> Tuple[int, int, int]:
        """
        Tryb przyrostowy: upsert raw ops po id_czynnosci, reagregacja
        statystyk TYLKO dla dotkniętych produktów.

        Zwraca (touched_products, raw_upserted, total_products_in_db).
        """
        touched_codes: Set[str] = set(df_clean["ProduktKod"].unique().tolist())
        print(f"💾 Zapis przyrostowy do SQLite: {self.db_path}")
        print(f"   • Produkty dotknięte zmianą: {len(touched_codes)}")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Zabezpieczenie: jeśli schemat raw ops jest stary, wymuś pełny tryb.
            if not self._raw_table_has_current_schema(cursor):
                raise RuntimeError(
                    "Schemat mes_raw_operations jest nieaktualny — wymagany tryb 'full'."
                )

            # 1) UPSERT surowych operacji
            rows_written = self._write_raw_ops(cursor, df_clean, opt_cols)
            print(f"   • Zapisano (INSERT OR REPLACE) rekordów raw ops: {rows_written:,}")

            # 2) Reagregacja tylko dla dotkniętych produktów
            placeholders = ",".join("?" * len(touched_codes))
            cursor.execute(f"""
                SELECT product_code, process_code, process_name, product_name,
                       client_code, real_time_per_unit_min
                FROM mes_raw_operations
                WHERE product_code IN ({placeholders});
            """, tuple(touched_codes))
            rows = cursor.fetchall()

            df_touched = pd.DataFrame(rows, columns=[
                "ProduktKod", "ProcesKod", "ProcesNazwa", "ProduktNazwa",
                "KlientKod", "CzasRealizacjiSztuka",
            ])
            df_touched["CzasRealizacjiSztuka"] = pd.to_numeric(
                df_touched["CzasRealizacjiSztuka"], errors="coerce"
            )
            df_touched = df_touched.dropna(subset=["CzasRealizacjiSztuka"])

            if not df_touched.empty:
                grouped, prod_grouped = _aggregate_process_stats(df_touched)

                cursor.execute(
                    f"DELETE FROM mes_process_stats WHERE product_code IN ({placeholders});",
                    tuple(touched_codes),
                )
                cursor.execute(
                    f"DELETE FROM product_profiles WHERE product_code IN ({placeholders});",
                    tuple(touched_codes),
                )
                self._write_stats(cursor, grouped, prod_grouped)

            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM product_profiles;")
            total_products = cursor.fetchone()[0]

            print(f"🎉 Baza zaktualizowana przyrostowo!")
            print(f"   • Zaktualizowanych produktów: {len(touched_codes):,}")
            print(f"   • Łącznie produktów w bazie: {total_products:,}")

            return len(touched_codes), rows_written, total_products
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Publiczne API
    # ------------------------------------------------------------------
    def process_and_save(self, mode: str = "auto") -> int:
        """
        Wczytuje, czyści, agreguje i zapisuje dane do SQLite.

        :param mode: 'auto' | 'full' | 'incremental'.
        :return: liczba unikalnych produktów w bazie po zapisie.
        """
        effective_mode = mode
        if mode == "auto":
            effective_mode = "incremental" if self.has_existing_data() else "full"
            print(f"🧭 Tryb 'auto' → wybrano: '{effective_mode}'")

        if effective_mode not in ("full", "incremental"):
            raise ValueError(f"Nieznany tryb: {mode!r}. Dozwolone: 'auto', 'full', 'incremental'.")

        print(f"🔄 Wczytywanie danych ze źródła: "
              f"{self.data_source.name if self.data_source else 'auto-detect'}")
        df_raw = self._load_data()
        print(f"📊 Załadowano {len(df_raw):,} wierszy (przed czyszczeniem).")

        df_clean = self._clean_dataframe(df_raw)
        print(f"✅ Po wyczyszczeniu: {len(df_clean):,} poprawnych operacji.")

        if df_clean.empty:
            print("⚠️ Brak poprawnych rekordów — nic do zapisania.")
            return 0

        opt_cols = self._detect_optional_columns(df_raw)

        if effective_mode == "full":
            unique_products, rows_written = self._save_full(df_clean, opt_cols)
            set_refresh_info(mode="full", rows_count=rows_written, db_path=self.db_path)
        else:
            touched, rows_written, unique_products = self._save_incremental(df_clean, opt_cols)
            set_refresh_info(mode="incremental", rows_count=rows_written, db_path=self.db_path)

        return unique_products


def get_product_profile(product_code: str, db_path: Optional[Union[str, Path]] = None) -> Optional[ProductProfile]:
    """Pobiera kompletny profil produktu wraz z procesami z bazy SQLite."""
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return None

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT product_code, client_code, product_name FROM product_profiles WHERE product_code = ?;",
            (product_code,),
        )
        prod_row = cursor.fetchone()
        if not prod_row:
            return None

        cursor.execute("""
            SELECT process_code, process_name,
                   median_time_min, min_time_min, max_time_min, sample_count,
                   q25_time_min, q50_time_min, q75_time_min
            FROM mes_process_stats
            WHERE product_code = ?
            ORDER BY process_code;
        """, (product_code,))
        process_rows = cursor.fetchall()

        processes = {}
        for row in process_rows:
            p_stat = ProcessTimeStat(
                process_code=row[0],
                process_name=row[1],
                median_time_per_unit_min=float(row[2]),
                min_time_per_unit_min=float(row[3]),
                max_time_per_unit_min=float(row[4]),
                sample_count=int(row[5]),
                q25_time_per_unit_min=float(row[6]),
                q50_time_per_unit_min=float(row[7]),
                q75_time_per_unit_min=float(row[8]),
            )
            processes[p_stat.process_code] = p_stat

        return ProductProfile(
            product_code=prod_row[0],
            client_code=prod_row[1],
            product_name=prod_row[2] or "",
            processes=processes,
        )
    finally:
        conn.close()


def get_all_product_profiles(db_path: Optional[Union[str, Path]] = None) -> List[ProductProfile]:
    """Pobiera listę profili wszystkich produktów z bazy SQLite."""
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return []

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_code, client_code, product_name FROM product_profiles ORDER BY product_code;")
        products = cursor.fetchall()
        return [
            ProductProfile(product_code=p[0], client_code=p[1], product_name=p[2] or "", processes={})
            for p in products
        ]
    finally:
        conn.close()


def get_raw_operations(
    product_code: str,
    process_code: str,
    db_path: Optional[Union[str, Path]] = None,
) -> List[RawOperation]:
    """Pobiera surowe odbicia MES dla danego produktu i procesu (analiza ZP-ków)."""
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return []

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT product_code, process_code, process_name, product_name, client_code,
                   dzial_zp, zp_number, zs_number, real_time_per_unit_min, unit_count,
                   planned_time_total_min, planned_time_per_unit_min,
                   norm_time_total_min, norm_time_per_unit_min
            FROM mes_raw_operations
            WHERE product_code = ? AND process_code = ?
            ORDER BY dzial_zp, zp_number, zs_number;
        """, (product_code, process_code))
        rows = cursor.fetchall()
        return [
            RawOperation(
                product_code=r[0],
                process_code=r[1],
                process_name=r[2],
                product_name=r[3],
                client_code=r[4],
                zp_number=r[6] or "—",
                zs_number=r[7] or "—",
                real_time_per_unit_min=float(r[8]),
                unit_count=int(r[9]) if r[9] is not None else 0,
                planned_time_total_min=float(r[10]) if r[10] is not None else None,
                planned_time_per_unit_min=float(r[11]) if r[11] is not None else None,
                norm_time_total_min=float(r[12]) if r[12] is not None else None,
                norm_time_per_unit_min=float(r[13]) if r[13] is not None else None,
                dzial_zp=(r[5] or None) if r[5] not in (None, "") else None,
            )
            for r in rows
        ]
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Przetwarzanie danych MES do bazy SQLite.")
    parser.add_argument("--source", type=str, default=None,
                        help="Ścieżka do pliku CSV lub XLSX (domyślnie: auto-detect z data/raw/).")
    parser.add_argument("--output", type=str, default=str(DB_PATH), help="Ścieżka do bazy SQLite.")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "full", "incremental"],
                        help="Tryb zapisu (auto: full przy pustej bazie, incremental gdy jest schemat).")
    args = parser.parse_args()

    if args.source:
        src_path = Path(args.source)
        suffix = src_path.suffix.lower()
        if suffix == ".csv":
            ds = CSVDataSource(src_path, separator=None, decimal=",")
        elif suffix in (".xlsx", ".xls"):
            ds = ExcelDataSource(src_path)
        else:
            raise ValueError(f"Nieobsługiwany format: {suffix}")
    else:
        ds = None  # auto-detect

    processor = MESProcessor(data_source=ds, db_path=args.output)
    processor.process_and_save(mode=args.mode)