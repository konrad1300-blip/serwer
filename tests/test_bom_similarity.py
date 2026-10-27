"""Testy jednostkowe dla składowej S_bom w silniku podobieństwa.

Sprawdzają:
- kształt S_bom (kompozycja precyzji i struktury),
- zgodność wyników z zadeklarowanymi wzorami,
- obsługę duplikatów kodów (agregacja ilości, nie nadpisywanie),
- spłaszczanie BOM (get_flattened_bom) — mnożenie ilości, ochrona przed cyklem,
  limit głębokości, „czarna skrzynka" gdy brak rozwinięcia,
- fallback w `find_similar()` gdy brak BOM (renormalizacja wag do klient/geom),
- integrację `find_similar_by_code()` ze ścieżką „kod + BOM" (bez DXF),
  w tym wariant B (brak BOM u kandydata = neutralne S_bom).
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.config import BOM_NEUTRAL_SIMILARITY
from src.models import BOMItem, DXFFeatures
from src.processors.bom_processor import (
    get_flattened_bom,
    get_product_bom,
)
from src.processors.similarity_engine import (
    SimilarityEngine,
    _compute_bom_similarity,
)


# ============================================================================
# Helpery — budowa BOMItem w testach
# ============================================================================
def _item(code: str, qty: float, *, semi: bool = False) -> BOMItem:
    """Buduje BOMItem z minimalnym zestawem pól."""
    return BOMItem(
        ptz_kod=code,
        ptz_nazwa=code,
        quantity=qty,
        unit="szt",
        stawka=0.0,
        wartosc_pln=0.0,
        typ="Materials",
        twr_typ=2 if semi else 1,
        is_semiproduct=semi,
    )


# ============================================================================
# _compute_bom_similarity
# ============================================================================
def test_bom_similarity_identical():
    """Identyczne BOM-y → S_bom = 1.0, wszystkie składowe = 1.0."""
    items = [_item("M0107-011", 30.0), _item("M0202-038", 56.0), _item("M0403-011", 20.0)]
    result = _compute_bom_similarity(items, items)

    assert result is not None
    assert result["s_bom"] == pytest.approx(1.0)
    assert result["precyzja"] == pytest.approx(1.0)
    assert result["struktura"] == pytest.approx(1.0)
    assert result["jaccard"] == pytest.approx(1.0)
    assert result["ilosc"] == pytest.approx(1.0)


def test_bom_similarity_handles_duplicate_codes():
    """
    Ten sam `ptz_kod` występujący wielokrotnie (np. bezpośrednio w wyrobie
    i przez półprodukt) MUSI być sumowany, nie nadpisywany.

    Regresja: wcześniej dict comprehension `{it.ptz_kod: it.quantity for ...}`
    zostawiał tylko ostatnią wartość, zaniżając ilość.

    Query: M0107-011 ×1 (bezpośrednio) + M0107-011 ×3 (przez półprodukt) → 4.
    Kandydat: M0107-011 ×4.
    Oczekiwane: identyczne ilości → S_ilość = 1.0, S_bom = 1.0.
    """
    q = [_item("M0107-011", 1.0), _item("M0107-011", 3.0)]
    c = [_item("M0107-011", 4.0)]

    result = _compute_bom_similarity(q, c)
    assert result is not None
    assert result["jaccard"] == pytest.approx(1.0)
    assert result["ilosc"] == pytest.approx(1.0)
    assert result["s_bom"] == pytest.approx(1.0)


def test_bom_similarity_duplicates_asymmetric():
    """
    Duplikaty u zapytania i u kandydata sumują się niezależnie — sprawdzamy,
    że S_ilość faktycznie porównuje sumy, a nie ostatnie wartości.

    Query: M0107-011 ×10 (jeden wpis).
    Kandydat: M0107-011 ×4 + M0107-011 ×6 = 10.
    Oczekiwane: identyczne sumy → S_ilość = 1.0.
    """
    q = [_item("M0107-011", 10.0)]
    c = [_item("M0107-011", 4.0), _item("M0107-011", 6.0)]

    result = _compute_bom_similarity(q, c)
    assert result is not None
    assert result["ilosc"] == pytest.approx(1.0)
    assert result["s_bom"] == pytest.approx(1.0)


def test_bom_similarity_no_common_codes():
    """
    Brak wspólnych kodów → Jaccard = 0.0, S_ilość = 0.0, S_precyzja = 0.0.
    Struktura może być wysoka, jeżeli kategorie się pokrywają.
    """
    q = [_item("M0107-011", 30.0), _item("M0202-038", 56.0)]
    c = [_item("M0105-005", 30.0), _item("M0204-005", 56.0)]

    result = _compute_bom_similarity(q, c)
    assert result is not None
    assert result["jaccard"] == pytest.approx(0.0)
    assert result["ilosc"] == pytest.approx(0.0)
    assert result["precyzja"] == pytest.approx(0.0)
    # Kategorie M01 i M02 są wspólne → struktura = 1.0.
    assert result["struktura"] == pytest.approx(1.0)
    # S_bom = 0.7·0.0 + 0.3·1.0 = 0.30.
    assert result["s_bom"] == pytest.approx(0.30)


def test_bom_similarity_precyzja_dominuje():
    """
    Precyzja waży więcej niż struktura (BOM_ALPHA_PRECYZJA = 0.70).
    Dwa scenariusze z identyczną strukturą, ale różną precyzją — kandydat
    z lepszą precyzją musi mieć wyższy S_bom.
    """
    q = [_item("M0107-011", 30.0), _item("M0202-038", 56.0), _item("M0403-011", 20.0)]
    same_codes_diff_qty = [
        _item("M0107-011", 45.0),  # +50% ilości
        _item("M0202-038", 84.0),  # +50%
        _item("M0403-011", 30.0),  # +50%
    ]
    diff_codes_same_cats = [
        _item("M0105-005", 30.0),
        _item("M0204-005", 56.0),
        _item("M0402-017", 20.0),
    ]

    res_same = _compute_bom_similarity(q, same_codes_diff_qty)
    res_diff = _compute_bom_similarity(q, diff_codes_same_cats)

    assert res_same["precyzja"] > res_diff["precyzja"]
    assert res_same["s_bom"] > res_diff["s_bom"]


def test_bom_similarity_partial_overlap():
    """
    Część wspólna kodów — wartości muszą mieścić się w (0, 1).

    Uwaga: `_compute_bom_similarity` zaokrągla wyniki w słowniku zwrotnym
    do 4 miejsc (spójnie z innymi wyjściami projektu), więc porównujemy
    do wartości zaokrąglonej — pełna precyzja `1/3` byłaby tu niespójna
    z kontraktem funkcji.
    """
    q = [_item("M0107-011", 30.0), _item("M0202-038", 56.0)]
    c = [_item("M0107-011", 30.0), _item("M0204-005", 56.0)]

    result = _compute_bom_similarity(q, c)
    assert result is not None
    assert 0.0 < result["s_bom"] < 1.0
    # Jaccard: 1 wspólny kod / 3 w sumie = 1/3, ale zwracane jako round(...,4).
    assert result["jaccard"] == round(1.0 / 3.0, 4)


def test_bom_similarity_empty_returns_none():
    """Pusty BOM po którejkolwiek stronie → None (brak oceny)."""
    assert _compute_bom_similarity([], [_item("M0107-011", 1.0)]) is None
    assert _compute_bom_similarity([_item("M0107-011", 1.0)], []) is None
    assert _compute_bom_similarity([], []) is None


# ============================================================================
# get_flattened_bom — spłaszczanie drzewa
# ============================================================================
@pytest.fixture
def bom_db():
    """Baza BOM z jednym wyrobem nadrzędnym, półproduktem i liściem."""
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "bom.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
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
        cur.execute("""
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

        # Wyrób nadrzędny: M0107-011 ×30 m² + półprodukt 029-0421-020 ×2 + M0202-017 ×12
        cur.execute("INSERT INTO bom_technologies VALUES ('029-0421-018', '029-0421-018', 'Plandeka Alubag', 0, 0, 3, 0.0, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-018', 'M0107-011', 'Tkanina MEHLER', 30.0, 'M2', 0, 0, 'Materials', 1, 0, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-018', '029-0421-020', 'Wzmocnienie narożnika', 2.0, 'szt', 0, 0, 'Materials', 2, 1, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-018', 'M0202-017', 'Oczko okrągłe 18', 12.0, 'szt', 0, 0, 'Materials', 1, 0, '2026-10-11');")

        # Półprodukt: M0107-009 ×5 m² + M0403-011 ×3 m + M0202-038 ×4
        cur.execute("INSERT INTO bom_technologies VALUES ('029-0421-020', '029-0421-020', 'Wzmocnienie', 0, 0, 3, 0.0, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-020', 'M0107-009', 'Tkanina inna', 5.0, 'M2', 0, 0, 'Materials', 1, 0, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-020', 'M0403-011', 'Taśma 043', 3.0, 'MTR', 0, 0, 'Materials', 1, 0, '2026-10-11');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-020', 'M0202-038', 'Oczko owalne 42x22', 4.0, 'szt', 0, 0, 'Materials', 1, 0, '2026-10-11');")

        conn.commit()
        conn.close()
        yield db


def test_flattened_bom_multiplies_quantities(bom_db):
    """
    Spłaszczenie: półprodukt ×2 → jego składniki mnożone przez 2.
    Oczekiwane liście:
      M0107-011 = 30, M0202-017 = 12,
      M0107-009 = 5 × 2 = 10,
      M0403-011 = 3 × 2 = 6,
      M0202-038 = 4 × 2 = 8.
    """
    items = get_flattened_bom("029-0421-018", db_path=bom_db)
    by_code = {it.ptz_kod: it for it in items}

    assert "029-0421-020" not in by_code, "Półprodukt powinien zostać rozwinięty."
    assert by_code["M0107-011"].quantity == pytest.approx(30.0)
    assert by_code["M0202-017"].quantity == pytest.approx(12.0)
    assert by_code["M0107-009"].quantity == pytest.approx(10.0)
    assert by_code["M0403-011"].quantity == pytest.approx(6.0)
    assert by_code["M0202-038"].quantity == pytest.approx(8.0)


def test_flattened_bom_missing_returns_empty():
    """Brak BOM dla kodu → pusta lista (bez wyjątku)."""
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "empty.sqlite"
        db.touch()  # plik istnieje, ale bez tabel
        assert get_flattened_bom("029-9999-999", db_path=db) == []


def test_flattened_bom_depth_limit():
    """
    Limit głębokości: łańcuch A → B → C → D → M0107-011, max_depth=2.

    Semantyka `depth` w `_flatten_recursive`:
    - `depth=1` — poziom produktu startowego (jego bezpośrednie dzieci),
    - `depth=2` — wnuki (rozwinięcie półproduktu pierwszego poziomu),
    - `depth > max_depth` — nie rozwijamy, pozycja zostaje „czarną skrzynką".

    Dla max_depth=2:
    - A (depth=1) rozwijane,
    - B (półprodukt, wywołanie depth=2) rozwijane,
    - C (półprodukt, wywołanie depth=3 > 2) — NIE rozwijane, zostaje jako
      czarna skrzynka w wyniku.
    Liście D i M0107-011 nie są widoczne.
    """
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "depth.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        # A → B → C → D → M0107-011 (każdy półprodukt z jednym dzieckiem)
        cur.execute("INSERT INTO bom_items VALUES ('A-1111-111', 'B-1111-111', 'B', 1, 'szt', 0, 0, '', 2, 1, '');")
        cur.execute("INSERT INTO bom_items VALUES ('B-1111-111', 'C-1111-111', 'C', 1, 'szt', 0, 0, '', 2, 1, '');")
        cur.execute("INSERT INTO bom_items VALUES ('C-1111-111', 'D-1111-111', 'D', 1, 'szt', 0, 0, '', 2, 1, '');")
        cur.execute("INSERT INTO bom_items VALUES ('D-1111-111', 'M0107-011', 'Tkanina', 7, 'M2', 0, 0, '', 1, 0, '');")
        for code in ("A-1111-111", "B-1111-111", "C-1111-111", "D-1111-111"):
            cur.execute("INSERT INTO bom_technologies VALUES (?, ?, ?, 0, 0, 0, 0, '');", (code, code, code))
        conn.commit()
        conn.close()

        items = get_flattened_bom("A-1111-111", max_depth=2, db_path=db)
        codes = {it.ptz_kod for it in items}

        # A rozwinięte → B rozwinięte → C zatrzymane jako czarna skrzynka.
        assert "C-1111-111" in codes
        # Poniżej limitu — nie rozwijamy dalej.
        assert "D-1111-111" not in codes
        assert "M0107-011" not in codes
        # C musi mieć flagę półproduktu (bo nie zostało rozwinięte).
        c_item = next(it for it in items if it.ptz_kod == "C-1111-111")
        assert c_item.is_semiproduct is True


def test_flattened_bom_cycle_protection():
    """
    Cykl A → B → A: rekurencja nie wpada w nieskończoną pętlę; A na
    drugim wystąpieniu zostaje jako czarna skrzynka.
    """
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "cycle.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        cur.execute("INSERT INTO bom_items VALUES ('A-1111-111', 'B-1111-111', 'B', 1, 'szt', 0, 0, '', 2, 1, '');")
        cur.execute("INSERT INTO bom_items VALUES ('B-1111-111', 'A-1111-111', 'A', 1, 'szt', 0, 0, '', 2, 1, '');")
        cur.execute("INSERT INTO bom_items VALUES ('B-1111-111', 'M0107-011', 'Tkanina', 5, 'M2', 0, 0, '', 1, 0, '');")
        for code in ("A-1111-111", "B-1111-111"):
            cur.execute("INSERT INTO bom_technologies VALUES (?, ?, ?, 0, 0, 0, 0, '');", (code, code, code))
        conn.commit()
        conn.close()

        items = get_flattened_bom("A-1111-111", db_path=db)
        codes = {it.ptz_kod for it in items}
        # Cykl przerwany: nie ma nieskończoności, tkanina z B jest widoczna.
        assert "M0107-011" in codes
        assert "B-1111-111" not in codes  # B rozwinięty


# ============================================================================
# Integracja z find_similar — fallback i użycie BOM
# ============================================================================
@pytest.fixture
def similarity_db_with_bom():
    """Baza z profilem, DXF-em i BOM-em dla dwóch kandydatów."""
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "sim.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        cur.execute("""
            CREATE TABLE product_dxf_features (
                product_code TEXT PRIMARY KEY, filename TEXT, filenames_json TEXT,
                files_count INTEGER, bounding_box_width_mm REAL, bounding_box_height_mm REAL,
                bounding_box_area_m2 REAL, total_cut_length_m REAL, drawing_length_m REAL,
                contours_count INTEGER, aspect_ratio REAL, layers_json TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)

        # Kandydaci
        cur.execute("INSERT INTO product_profiles VALUES ('029-001', '029', 'Kandydat A', 15, 3, 10);")
        cur.execute("INSERT INTO product_dxf_features VALUES ('029-001', 'a.dxf', '[\"a.dxf\"]', 1, 1000, 500, 0.5, 3.0, 0.5, 4, 2.0, '[]');")
        cur.execute("INSERT INTO bom_technologies VALUES ('029-001', '029-001', 'A', 0, 0, 3, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-001', 'M0403-011', 'Tś', 20, 'MTR', 0, 0, '', 1, 0, '');")

        cur.execute("INSERT INTO product_profiles VALUES ('029-002', '029', 'Kandydat B', 20, 4, 15);")
        cur.execute("INSERT INTO product_dxf_features VALUES ('029-002', 'b.dxf', '[\"b.dxf\"]', 1, 1000, 500, 0.5, 3.0, 0.5, 4, 2.0, '[]');")
        cur.execute("INSERT INTO bom_technologies VALUES ('029-002', '029-002', 'B', 0, 0, 2, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-002', 'M0105-005', 'T2', 30, 'M2', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-002', 'M0204-005', 'H', 56, 'szt', 0, 0, '', 1, 0, '');")

        # Zapytanie ma BOM
        cur.execute("INSERT INTO bom_technologies VALUES ('029-0926-001', '029-0926-001', 'Q', 0, 0, 3, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0403-011', 'Tś', 20, 'MTR', 0, 0, '', 1, 0, '');")

        conn.commit()
        conn.close()
        yield db


def test_find_similar_uses_bom_when_available(similarity_db_with_bom):
    """
    Zapytanie ma BOM, kandydaci też → S_bom wchodzi do wyniku.
    Kandydat A (identyczny BOM) powinien dostać bom_used=True i S_bom=1.0,
    Kandydat B (inny BOM) → niższe S_bom.
    """
    engine = SimilarityEngine(db_path=similarity_db_with_bom)
    query_features = DXFFeatures(
        filename="q.dxf", bounding_box_width_mm=1000, bounding_box_height_mm=500,
        bounding_box_area_m2=0.5, total_cut_length_m=3.0, drawing_length_m=0.5,
        contours_count=4, aspect_ratio=2.0,
    )
    matches = engine.find_similar("029-0926-001", query_features, top_k=5)

    by_code = {m.matched_product_code: m for m in matches}
    a = by_code["029-001"]
    b = by_code["029-002"]

    assert a.bom_used is True
    assert a.bom_similarity == pytest.approx(1.0)
    assert b.bom_used is True
    assert b.bom_similarity is not None
    assert b.bom_similarity < a.bom_similarity
    assert a.similarity_score > b.similarity_score


def test_find_similar_fallback_without_bom():
    """
    Brak tabel BOM → S_bom pomijane, wagi renormalizowane do klient/geom.
    Kandydat zgodny klientem i geometrią identyczną → S = 1.0.
    """
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "no_bom.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        cur.execute("""
            CREATE TABLE product_dxf_features (
                product_code TEXT PRIMARY KEY, filename TEXT, filenames_json TEXT,
                files_count INTEGER, bounding_box_width_mm REAL, bounding_box_height_mm REAL,
                bounding_box_area_m2 REAL, total_cut_length_m REAL, drawing_length_m REAL,
                contours_count INTEGER, aspect_ratio REAL, layers_json TEXT
            );
        """)
        cur.execute("INSERT INTO product_profiles VALUES ('029-001', '029', 'A', 15, 3, 10);")
        cur.execute("INSERT INTO product_dxf_features VALUES ('029-001', 'a.dxf', '[\"a.dxf\"]', 1, 1000, 500, 0.5, 3.0, 0.5, 4, 2.0, '[]');")
        conn.commit()
        conn.close()

        engine = SimilarityEngine(db_path=db)
        query_features = DXFFeatures(
            filename="q.dxf", bounding_box_width_mm=1000, bounding_box_height_mm=500,
            bounding_box_area_m2=0.5, total_cut_length_m=3.0, drawing_length_m=0.5,
            contours_count=4, aspect_ratio=2.0,
        )
        matches = engine.find_similar("029-0926-001", query_features, top_k=5)

        assert len(matches) == 1
        m = matches[0]
        assert m.bom_used is False
        assert m.bom_similarity is None
        # Klient zgodny + geometria identyczna → S = 1.0 (po renormalizacji).
        assert m.similarity_score == pytest.approx(1.0)


# ============================================================================
# Integracja: find_similar_by_code ze ścieżką kod + BOM (bez DXF)
# ============================================================================
def test_find_similar_by_code_with_bom_path():
    """
    Integracja: gdy zapytanie i przynajmniej jeden kandydat mają BOM,
    `find_similar_by_code()` wybiera ścieżkę 2-składnikową (klient + BOM).
    Sprawdza wzór S = (w_klient·1 + w_bom·S_bom) / (w_klient + w_bom).
    """
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "code_bom.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        cur.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        # Zapytanie + identyczny kandydat (oba z BOM).
        cur.execute("INSERT INTO product_profiles VALUES ('029-0926-001', '029', 'Q', 15.0, 3, 10);")
        cur.execute("INSERT INTO product_profiles VALUES ('029-0421-018', '029', 'A', 15.0, 3, 10);")
        for code in ("029-0926-001", "029-0421-018"):
            cur.execute("INSERT INTO bom_technologies VALUES (?, ?, ?, 0, 0, 2, 0, '');", (code, code, code))
            cur.execute("INSERT INTO bom_items VALUES (?, 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');", (code,))
            cur.execute("INSERT INTO bom_items VALUES (?, 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');", (code,))
        conn.commit()
        conn.close()

        engine = SimilarityEngine(
            db_path=db, weight_client=0.15, weight_geom=0.45, weight_bom=0.40,
        )
        matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=5)

        assert len(matches) == 2
        assert all(m.bom_used for m in matches)
        # S = (0.15·1 + 0.40·1) / 0.55 = 1.0 dla identycznego BOM-u.
        for m in matches:
            assert m.similarity_score == pytest.approx(1.0)


def test_find_similar_by_code_neutral_bom_for_missing_candidate():
    """
    Wariant B: w ścieżce kod + BOM kandydat BEZ BOM-u wchodzi do rankingu
    z neutralnym S_bom = 0.5 (bez wykluczenia).

    Weryfikuje wynik formułą: S = (w_klient·1 + w_bom·0.5) / (w_klient + w_bom).
    Dla w_klient=0.15, w_bom=0.40: S = (0.15 + 0.20) / 0.55 ≈ 0.6364.
    """
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "code_bom_mixed.sqlite"
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        cur.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        # Kandydat z BOM (identyczny) + kandydat BEZ BOM.
        cur.execute("INSERT INTO product_profiles VALUES ('029-0421-018', '029', 'Z BOM', 15, 3, 10);")
        cur.execute("INSERT INTO product_profiles VALUES ('029-0421-019', '029', 'Bez BOM', 12, 3, 8);")
        cur.execute("INSERT INTO bom_technologies VALUES ('029-0421-018', '029-0421-018', 'A', 0, 0, 2, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-018', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0421-018', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        # Zapytanie ma BOM (bez wpisu w product_profiles).
        cur.execute("INSERT INTO bom_technologies VALUES ('029-0926-001', '029-0926-001', 'Q', 0, 0, 2, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        cur.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        conn.commit()
        conn.close()

        engine = SimilarityEngine(
            db_path=db, weight_client=0.15, weight_geom=0.45, weight_bom=0.40,
        )
        matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=5)

        codes = {m.matched_product_code for m in matches}
        assert "029-0421-018" in codes
        assert "029-0421-019" in codes

        with_bom = next(m for m in matches if m.matched_product_code == "029-0421-018")
        without_bom = next(m for m in matches if m.matched_product_code == "029-0421-019")

        # Z BOM, identyczny → S_bom=1.0 → S = 1.0
        assert with_bom.bom_used is True
        assert with_bom.similarity_score == pytest.approx(1.0)

        # Bez BOM → S_bom=0.5 neutralne → S ≈ 0.6364
        assert without_bom.bom_used is False
        assert without_bom.bom_similarity is None
        assert without_bom.similarity_score == pytest.approx(
            (0.15 * 1.0 + 0.40 * BOM_NEUTRAL_SIMILARITY) / (0.15 + 0.40),
            abs=1e-3,
        )