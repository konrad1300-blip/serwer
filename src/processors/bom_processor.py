"""Moduł przetwarzania BOM (Bill of Materials) z ERP XL (Procesor 5).

Parsuje widok `_im_mm_kalkulacja_Excel`, wybiera dla każdego rdzenia produktu
(`XXX-XXXX-XXX`) technologię w najnowszej rewizji i wersji, agreguje duplikaty
materiałów po `PTZ_Kod` i zapisuje do SQLite (tabele `bom_technologies`,
`bom_items` w tej samej bazie co MES).

Reguły biznesowe:
- rdzeń kodu: `XXX-XXXX-XXX` — łączy BOM z MES-em po `ProduktKod`.
- sufiks opcjonalny: `_RxxVxx` (rewizja i wersja, zawsze dwucyfrowe).
  Gdy sufiks nie pasuje do wzorca, traktujemy cały kod jako rdzeń (rewizja=0).
- wybieramy ZAWSZE najnowszą rewizję, a w niej najnowszą wersję.
- duplikaty `PTZ_Kod` w obrębie jednej technologii: sumujemy ilości i wartości.
"""
import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple, Union

import pandas as pd

from src.config import BOM_MAX_DEPTH, DB_PATH, PROCESSED_DATA_DIR
from src.db_metadata import set_metadata
from src.models import BOMItem, BOMTechnology
from src.processors.data_source import (
    BOMDataSource,
    CSVDataSource,
    DataSource,
    ExcelDataSource,
)


# Wymagane kolumny w widoku/pliku BOM.
REQUIRED_BOM_COLUMNS = {
    "PTE_Kod", "PTE_Nazwa", "PTZ_Kod", "PTZ_nazwa",
    "ilość", "Jednostka", "Stawka", "Wartosc PLN", "Twr_Typ",
}

# Wzorce parsowania kodów.
_CORE_CODE_RE = re.compile(r"^(\d{3}-\d{4}-\d{3})$")
_FULL_TECH_CODE_RE = re.compile(r"^(\d{3}-\d{4}-\d{3})_R(\d{2})V(\d{2})$")
_SEMIPRODUCT_PREFIX_RE = re.compile(r"^\d{3}-\d{4}-\d{3}")


# ------------------------------------------------------------------------------
# PARSOWANIE KODÓW
# ------------------------------------------------------------------------------
def parse_pte_kod(pte_kod: str) -> Optional[Tuple[str, int, int]]:
    """
    Rozbiera kod technologii na (rdzeń, rewizja, wersja).

    - `111-1111-111` → ('111-1111-111', 0, 0)
    - `111-1111-111_R01V02` → ('111-1111-111', 1, 2)
    - cokolwiek innego → None (wiersz pomijany przy budowie bazy BOM).

    :param pte_kod: surowy kod technologii z widoku ERP.
    :return: krotka (rdzeń, revision, version) lub None jeśli kod nie pasuje.
    """
    if not pte_kod or not isinstance(pte_kod, str):
        return None
    kod = pte_kod.strip()

    m = _FULL_TECH_CODE_RE.match(kod)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3))

    m = _CORE_CODE_RE.match(kod)
    if m:
        return m.group(1), 0, 0

    return None


def is_semiproduct_kod(ptz_kod: str, twr_typ: Optional[int]) -> bool:
    """
    Klasyfikuje pozycję BOM jako półprodukt.

    Kryteria (spełnione którekolwiek):
    - `Twr_Typ == 2` (ERP jawnie oznacza towar jako produkt/półprodukt),
    - `PTZ_Kod` zaczyna się od formatu `XXX-XXXX-XXX`.
    """
    if twr_typ == 2:
        return True
    if ptz_kod and isinstance(ptz_kod, str) and _SEMIPRODUCT_PREFIX_RE.match(ptz_kod.strip()):
        return True
    return False


# ------------------------------------------------------------------------------
# PRZETWARZANIE
# ------------------------------------------------------------------------------
def _safe_float(val) -> float:
    """Konwertuje wartość na float (obsługa przecinka dziesiętnego i pustych)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val) -> int:
    """Konwertuje wartość na int (bezpiecznie)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


class BOMProcessor:
    """
    Wczytuje, czyści, agreguje BOM z widoku ERP i zapisuje do SQLite.

    Zawsze w trybie pełnym — BOM nie ma znacznika przyrostowego.
    """

    def __init__(
        self,
        data_source: Optional[DataSource] = None,
        db_path: Optional[Union[str, Path]] = None,
    ):
        self.data_source = data_source
        self.db_path = Path(db_path) if db_path else DB_PATH

    # ------------------------------------------------------------------
    # Wczytywanie i czyszczenie
    # ------------------------------------------------------------------
    def _load_data(self) -> pd.DataFrame:
        """Wczytuje DataFrame ze źródła i waliduje wymagane kolumny."""
        if self.data_source is None:
            self.data_source = BOMDataSource()

        df = self.data_source.load()
        missing = REQUIRED_BOM_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Źródło '{self.data_source.name}' nie zawiera wymaganych kolumn: "
                f"{sorted(missing)}. Znalezione kolumny: {sorted(df.columns.tolist())}."
            )
        return df

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Czyści DataFrame BOM:
        - normalizuje kody (`PTE_Kod`, `PTZ_Kod`) — strip,
        - konwertuje ilości i stawki na float,
        - pomija wiersze z PTE_Kod niepasującym do wzorca rdzenia.
        """
        df = df.copy()

        df["PTE_Kod"] = df["PTE_Kod"].astype(str).str.strip()
        df["PTZ_Kod"] = df["PTZ_Kod"].astype(str).str.strip()
        df["PTZ_nazwa"] = df["PTZ_nazwa"].fillna("").astype(str).str.strip()
        df["PTE_Nazwa"] = df["PTE_Nazwa"].fillna("").astype(str).str.strip()
        df["Jednostka"] = df["Jednostka"].fillna("").astype(str).str.strip()
        df["Typ"] = df["Typ"].fillna("").astype(str).str.strip()

        df["quantity"] = df["ilość"].apply(_safe_float)
        df["stawka"] = df["Stawka"].apply(_safe_float)
        df["wartosc_pln"] = df["Wartosc PLN"].apply(_safe_float)
        df["twr_typ"] = df["Twr_Typ"].apply(_safe_int)

        # Parsowanie rdzenia + rewizji/wersji.
        parsed = df["PTE_Kod"].apply(parse_pte_kod)
        df["core_code"] = parsed.apply(lambda t: t[0] if t else None)
        df["revision"] = parsed.apply(lambda t: t[1] if t else 0)
        df["version"] = parsed.apply(lambda t: t[2] if t else 0)

        # Wiersze bez poprawnego rdzenia — pomijamy.
        df = df[df["core_code"].notna()].copy()

        return df

    # ------------------------------------------------------------------
    # Wybór najnowszej technologii
    # ------------------------------------------------------------------
    def _pick_latest_per_core(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Dla każdego rdzenia wybiera wiersze technologii o najnowszej rewizji,
        a w niej — najnowszej wersji.

        Sortowanie: revision DESC, version DESC. Tie-break nie jest potrzebny,
        bo (revision, version) jest unikalne per rdzeń w praktyce — jeśli nie
        jest (błąd danych), bierzemy pierwszy wiersz po sortowaniu.
        """
        df_sorted = df.sort_values(
            by=["core_code", "revision", "version"],
            ascending=[True, False, False],
        )
        latest = (
            df_sorted
            .groupby("core_code", as_index=False)
            .first()
            [["core_code", "PTE_Kod", "revision", "version"]]
        )
        # Dołączamy z powrotem wszystkie wiersze, które odpowiadają wybranej
        # kombinacji (core, revision, version). W praktyce jeden wiersz na
        # materiał, ale może być wiele pozycji.
        merged = df.merge(
            latest,
            on=["core_code", "revision", "version"],
            how="inner",
            suffixes=("", "_latest"),
        )
        return merged

    # ------------------------------------------------------------------
    # Agregacja pozycji BOM
    # ------------------------------------------------------------------
    def _aggregate_items(self, df: pd.DataFrame) -> List[BOMTechnology]:
        """
        Buduje listę technologii BOM (jedna na rdzeń) z zagregowanymi pozycjami.

        Agregacja duplikatów: grupujemy po `(core_code, PTZ_Kod)` i sumujemy
        `quantity` oraz `wartosc_pln`. Pozostałe pola (nazwa, jednostka,
        stawka, typ) bierzemy z pierwszego napotkanego wiersza.
        """
        technologies: List[BOMTechnology] = []

        for core_code, group in df.groupby("core_code"):
            # Metadane technologii — z pierwszego wiersza grupy.
            first = group.iloc[0]
            full_code = str(first["PTE_Kod"])
            pte_nazwa = str(first["PTE_Nazwa"])
            revision = int(first["revision"])
            version = int(first["version"])

            # Agregacja duplikatów po PTZ_Kod.
            agg = (
                group.groupby("PTZ_Kod", as_index=False)
                .agg({
                    "quantity": "sum",
                    "wartosc_pln": "sum",
                    "stawka": "first",
                    "Jednostka": "first",
                    "PTZ_nazwa": "first",
                    "Typ": "first",
                    "twr_typ": "first",
                })
            )

            items: List[BOMItem] = []
            for _, row in agg.iterrows():
                ptz = str(row["PTZ_Kod"])
                twr = int(row["twr_typ"])
                items.append(BOMItem(
                    ptz_kod=ptz,
                    ptz_nazwa=str(row["PTZ_nazwa"]),
                    quantity=round(float(row["quantity"]), 4),
                    unit=str(row["Jednostka"]),
                    stawka=round(float(row["stawka"]), 4),
                    wartosc_pln=round(float(row["wartosc_pln"]), 4),
                    typ=str(row["Typ"]),
                    twr_typ=twr,
                    is_semiproduct=is_semiproduct_kod(ptz, twr),
                ))

            items.sort(key=lambda i: i.ptz_kod)

            technologies.append(BOMTechnology(
                product_code=core_code,
                full_pte_kod=full_code,
                pte_nazwa=pte_nazwa,
                revision=revision,
                version=version,
                items=items,
            ))

        return technologies

    # ------------------------------------------------------------------
    # Zapis do SQLite
    # ------------------------------------------------------------------
    def _create_schema(self, cursor: sqlite3.Cursor) -> None:
        """Tworzy tabele BOM (DROP + CREATE — pełny refresh)."""
        cursor.execute("DROP TABLE IF EXISTS bom_items;")
        cursor.execute("DROP TABLE IF EXISTS bom_technologies;")

        cursor.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY,
                full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0,
                items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0,
                fetched_at TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL,
                ptz_kod TEXT NOT NULL,
                ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0,
                unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0,
                wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT,
                twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)

    def _save(self, technologies: List[BOMTechnology]) -> int:
        """Zapisuje technologie i pozycje do SQLite. Zwraca liczbę technologii."""
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        fetched_at = datetime.now().isoformat(timespec="seconds")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            self._create_schema(cursor)

            tech_rows = []
            item_rows = []
            for tech in technologies:
                tech_rows.append((
                    tech.product_code,
                    tech.full_pte_kod,
                    tech.pte_nazwa,
                    tech.revision,
                    tech.version,
                    tech.items_count,
                    round(tech.total_value_pln, 4),
                    fetched_at,
                ))
                for it in tech.items:
                    item_rows.append((
                        tech.product_code,
                        it.ptz_kod,
                        it.ptz_nazwa,
                        it.quantity,
                        it.unit,
                        it.stawka,
                        it.wartosc_pln,
                        it.typ,
                        it.twr_typ,
                        1 if it.is_semiproduct else 0,
                        fetched_at,
                    ))

            cursor.executemany(
                "INSERT OR REPLACE INTO bom_technologies VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                tech_rows,
            )
            cursor.executemany(
                "INSERT OR REPLACE INTO bom_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                item_rows,
            )

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bom_items_ptz ON bom_items(ptz_kod);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bom_items_semi ON bom_items(is_semiproduct);")

            conn.commit()
            return len(tech_rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Publiczne API
    # ------------------------------------------------------------------
    def process_and_save(self) -> int:
        """
        Pełny pipeline: wczytaj → wyczyść → wybierz najnowsze → agreguj → zapisz.

        :return: liczba technologii zapisanych do bazy.
        """
        print(f"🔄 Wczytywanie BOM ze źródła: "
              f"{self.data_source.name if self.data_source else 'auto-detect (BOM ERP)'}")
        df_raw = self._load_data()
        print(f"📊 Załadowano {len(df_raw):,} wierszy (przed czyszczeniem).")

        df_clean = self._clean_dataframe(df_raw)
        dropped = len(df_raw) - len(df_clean)
        if dropped:
            print(f"⚠️ Pominięto {dropped:,} wierszy bez rozpoznanego rdzenia kodu.")
        print(f"✅ Po wyczyszczeniu: {len(df_clean):,} wierszy.")

        if df_clean.empty:
            print("⚠️ Brak poprawnych rekordów — nic do zapisania.")
            return 0

        df_latest = self._pick_latest_per_core(df_clean)
        print(f"🔍 Wybrano wiersze najnowszych technologii dla "
              f"{df_latest['core_code'].nunique():,} rdzeni produktu.")

        technologies = self._aggregate_items(df_latest)
        count = self._save(technologies)

        total_items = sum(t.items_count for t in technologies)
        total_value = sum(t.total_value_pln for t in technologies)

        set_metadata("last_bom_refresh_at", datetime.now().isoformat(timespec="seconds"), self.db_path)
        set_metadata("last_bom_refresh_rows", str(len(df_raw)), self.db_path)
        set_metadata("last_bom_refresh_tech", str(count), self.db_path)

        print(f"🎉 Baza BOM zaktualizowana!")
        print(f"   • Technologie (rdzenie): {count:,}")
        print(f"   • Pozycje BOM (po agregacji): {total_items:,}")
        print(f"   • Sumaryczna wartość: {total_value:,.2f} PLN")

        return count


# ==============================================================================
# ODCZYT Z BAZY
# ==============================================================================
def get_product_bom(
    product_code: str,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[BOMTechnology]:
    """
    Pobiera technologię BOM dla danego rdzenia produktu.

    :param product_code: rdzeń kodu (np. '029-0421-018') — bez sufiksu R/V.
    :param db_path: ścieżka do bazy; domyślnie DB_PATH.
    :return: BOMTechnology lub None jeśli brak.
    """
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return None

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT product_code, full_pte_kod, pte_nazwa, revision, version
                FROM bom_technologies
                WHERE product_code = ?;
            """, (product_code,))
        except sqlite3.OperationalError:
            return None

        tech_row = cursor.fetchone()
        if not tech_row:
            return None

        cursor.execute("""
            SELECT ptz_kod, ptz_nazwa, quantity, unit, stawka, wartosc_pln,
                   typ, twr_typ, is_semiproduct
            FROM bom_items
            WHERE product_code = ?
            ORDER BY ptz_kod;
        """, (product_code,))
        item_rows = cursor.fetchall()

        items = [
            BOMItem(
                ptz_kod=r[0],
                ptz_nazwa=r[1] or "",
                quantity=float(r[2]),
                unit=r[3] or "",
                stawka=float(r[4]),
                wartosc_pln=float(r[5]),
                typ=r[6] or "",
                twr_typ=int(r[7]),
                is_semiproduct=bool(r[8]),
            )
            for r in item_rows
        ]

        return BOMTechnology(
            product_code=tech_row[0],
            full_pte_kod=tech_row[1],
            pte_nazwa=tech_row[2] or "",
            revision=int(tech_row[3]),
            version=int(tech_row[4]),
            items=items,
        )
    finally:
        conn.close()


def get_all_bom_products(db_path: Optional[Union[str, Path]] = None) -> List[dict]:
    """
    Zwraca listę wszystkich produktów mających BOM (do selectboxa w UI).

    :return: lista dictów {product_code, full_pte_kod, pte_nazwa,
             revision, version, items_count, total_value_pln}.
    """
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return []

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT product_code, full_pte_kod, pte_nazwa, revision, version,
                       items_count, total_value_pln
                FROM bom_technologies
                ORDER BY product_code;
            """)
        except sqlite3.OperationalError:
            return []

        return [
            {
                "product_code": r[0],
                "full_pte_kod": r[1],
                "pte_nazwa": r[2] or "",
                "revision": int(r[3]),
                "version": int(r[4]),
                "items_count": int(r[5]),
                "total_value_pln": float(r[6]),
            }
            for r in cursor.fetchall()
        ]
    finally:
        conn.close()


# ==============================================================================
# SPŁASZCZANIE BOM (do silnika podobieństwa)
# ==============================================================================
def _flatten_recursive(
    product_code: str,
    multiplier: float,
    depth: int,
    visited: Set[str],
    db_path: Path,
    max_depth: int,
) -> List[BOMItem]:
    """
    Rekurencyjnie rozwija BOM do liści (materiałów `Mxxxx-xxx`).

    - Półprodukty (`is_semiproduct=True`) rozwijane są o własny BOM
      pomnożony przez `multiplier × quantity`.
    - Cykle są wykrywane przez `visited` (jeśli kod już odwiedzony na tej
      ścieżce — nie wchodzimy ponownie).
    - Limit `max_depth` chroni przed nieskończoną rekurencją i przeładowaniem UI.
    - Jeśli półprodukt nie ma własnego BOM w bazie lub rozwinięcie zwróci
      pustą listę (cykl/głębokość) — zostaje zachowany jako „czarna skrzynka"
      z `is_semiproduct=True`.
    """
    if depth > max_depth or product_code in visited:
        return []

    visited_next = visited | {product_code}
    bom = get_product_bom(product_code, db_path=db_path)
    if bom is None:
        return []

    result: List[BOMItem] = []
    for it in bom.items:
        effective_qty = multiplier * it.quantity

        if it.is_semiproduct:
            sub_items = _flatten_recursive(
                it.ptz_kod, effective_qty, depth + 1, visited_next, db_path, max_depth,
            )
            if sub_items:
                result.extend(sub_items)
            else:
                # Brak rozwinięcia — czarna skrzynka (zachowujemy dla struktury).
                result.append(BOMItem(
                    ptz_kod=it.ptz_kod,
                    ptz_nazwa=it.ptz_nazwa,
                    quantity=round(effective_qty, 4),
                    unit=it.unit,
                    stawka=it.stawka,
                    wartosc_pln=round(it.wartosc_pln * multiplier, 4),
                    typ=it.typ,
                    twr_typ=it.twr_typ,
                    is_semiproduct=True,
                ))
        else:
            result.append(BOMItem(
                ptz_kod=it.ptz_kod,
                ptz_nazwa=it.ptz_nazwa,
                quantity=round(effective_qty, 4),
                unit=it.unit,
                stawka=it.stawka,
                wartosc_pln=round(it.wartosc_pln * multiplier, 4),
                typ=it.typ,
                twr_typ=it.twr_typ,
                is_semiproduct=False,
            ))
    return result


def get_flattened_bom(
    product_code: str,
    max_depth: int = BOM_MAX_DEPTH,
    db_path: Optional[Union[str, Path]] = None,
) -> List[BOMItem]:
    """
    Zwraca BOM wyrobu spłaszczony do liści (materiałów).

    Każdy półprodukt jest rozwijany rekurencyjnie (z mnożeniem ilości),
    z ochroną przed cyklem i limitem `max_depth`. Półprodukty, których
    nie da się rozwinąć (brak BOM w bazie, cykl, przekroczona głębokość),
    pozostają w wyniku jako „czarne skrzynki" (`is_semiproduct=True`).

    Ilości w wyniku są już przemnożone przez iloczyn ilości ze wszystkich
    poziomów drzewa (np. półprodukt ×2, w nim tkanina 5 m² → wynik 10 m²).

    :param product_code: rdzeń kodu produktu (np. '029-0421-018').
    :param max_depth: maksymalna głębokość rozwinięcia (domyślnie z configu).
    :param db_path: ścieżka do bazy; domyślnie DB_PATH.
    :return: lista BOMItem (może być pusta, gdy brak BOM lub bazy).
    """
    db_file = Path(db_path) if db_path else DB_PATH
    if not db_file.exists():
        return []
    return _flatten_recursive(
        product_code=product_code,
        multiplier=1.0,
        depth=1,
        visited=set(),
        db_path=db_file,
        max_depth=max_depth,
    )


# ==============================================================================
# CLI
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Przetwarzanie BOM z ERP XL do bazy SQLite.")
    parser.add_argument("--source", type=str, default=None,
                        help="Ścieżka do pliku CSV lub XLSX (domyślnie: BOM z ERP).")
    parser.add_argument("--output", type=str, default=str(DB_PATH), help="Ścieżka do bazy SQLite.")
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
        ds = None  # auto: BOM z ERP

    processor = BOMProcessor(data_source=ds, db_path=args.output)
    processor.process_and_save()