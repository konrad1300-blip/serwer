"""Testy jednostkowe dla silnika dopasowania (DXF + kod + BOM oraz tylko-kod)."""
import sqlite3
import tempfile
from pathlib import Path
import pytest

from src.config import BOM_NEUTRAL_SIMILARITY
from src.models import DXFFeatures
from src.processors.similarity_engine import (
    SimilarityEngine,
    _month_distance,
    _parse_product_code,
)


# ============================================================================
# Fixtury
# ============================================================================
@pytest.fixture
def mock_similarity_db():
    """Baza z pełnym schematem (profiles + dxf) — do testów trybu hybrydowego."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_sim.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY,
                client_code TEXT,
                product_name TEXT,
                total_median_time_min REAL,
                process_count INTEGER,
                total_samples INTEGER
            );
        """)
        c.execute("""
            CREATE TABLE product_dxf_features (
                product_code TEXT PRIMARY KEY,
                filename TEXT,
                filenames_json TEXT,
                files_count INTEGER,
                bounding_box_width_mm REAL,
                bounding_box_height_mm REAL,
                bounding_box_area_m2 REAL,
                total_cut_length_m REAL,
                drawing_length_m REAL,
                contours_count INTEGER,
                aspect_ratio REAL,
                layers_json TEXT
            );
        """)

        c.execute("INSERT INTO product_profiles VALUES ('029-001', '029', 'Idealny', 15.0, 3, 10);")
        c.execute("INSERT INTO product_dxf_features VALUES ('029-001', '029-001.dxf', '[\"029-001.dxf\"]', 1, 1000.0, 500.0, 0.5, 3.0, 0.5, 4, 2.0, '[]');")

        c.execute("INSERT INTO product_profiles VALUES ('029-002', '029', 'Inny geom.', 30.0, 4, 15);")
        c.execute("INSERT INTO product_dxf_features VALUES ('029-002', '029-002.dxf', '[\"029-002.dxf\"]', 1, 3000.0, 2000.0, 6.0, 10.0, 1.0, 10, 1.5, '[]');")

        c.execute("INSERT INTO product_profiles VALUES ('066-001', '066', 'Bliźniak', 12.0, 2, 5);")
        c.execute("INSERT INTO product_dxf_features VALUES ('066-001', '066-001.dxf', '[\"066-001.dxf\"]', 1, 1000.0, 500.0, 0.5, 3.0, 0.5, 4, 2.0, '[]');")

        conn.commit()
        conn.close()
        yield db_path


@pytest.fixture
def mock_code_only_db():
    """Baza z samymi profilami produktów (bez DXF, bez BOM) — tryb tylko-kod fallback."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_code.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY,
                client_code TEXT,
                product_name TEXT,
                total_median_time_min REAL,
                process_count INTEGER,
                total_samples INTEGER
            );
        """)
        c.execute("INSERT INTO product_profiles VALUES ('029-0926-001', '029', 'Bliski data', 15.0, 4, 10);")
        c.execute("INSERT INTO product_profiles VALUES ('029-0421-018', '029', 'Stary, dużo prób', 20.0, 5, 200);")
        c.execute("INSERT INTO product_profiles VALUES ('029-0626-005', '029', 'Bliski, mało prób', 12.0, 3, 2);")
        c.execute("INSERT INTO product_profiles VALUES ('065-0926-004', '065', 'Inny klient', 18.0, 4, 5);")
        conn.commit()
        conn.close()
        yield db_path


@pytest.fixture
def mock_code_with_bom_db():
    """
    Baza z profilami i BOM-em. Zapytanie 029-0926-001 ma BOM (bez własnego
    profilu — traktujemy je jako nowe zapytanie). Kandydaci:
    - 029-001: BOM identyczny z zapytaniem,
    - 029-002: BOM podobny strukturalnie (te same kategorie, inne kody),
    - 029-003: brak BOM-u.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_code_bom.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY,
                client_code TEXT,
                product_name TEXT,
                total_median_time_min REAL,
                process_count INTEGER,
                total_samples INTEGER
            );
        """)
        c.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)

        # Kandydaci (wszyscy klienta 029, żeby przeszli filtr).
        c.execute("INSERT INTO product_profiles VALUES ('029-001', '029', 'Bliźniak BOM', 15.0, 3, 10);")
        c.execute("INSERT INTO product_profiles VALUES ('029-002', '029', 'Inne materiały', 20.0, 4, 15);")
        c.execute("INSERT INTO product_profiles VALUES ('029-003', '029', 'Bez BOM', 10.0, 2, 5);")

        # Zapytanie ma BOM (bez profilu w product_profiles).
        c.execute("INSERT INTO bom_technologies VALUES ('029-0926-001', '029-0926-001', 'Q', 0, 0, 3, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0107-011', 'Tkanina', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0202-038', 'Oczko', 56, 'szt', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0403-011', 'Taśma', 20, 'MTR', 0, 0, '', 1, 0, '');")

        # Kandydat 029-001 — identyczny BOM.
        c.execute("INSERT INTO bom_technologies VALUES ('029-001', '029-001', 'A', 0, 0, 3, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-001', 'M0107-011', 'Tkanina', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-001', 'M0202-038', 'Oczko', 56, 'szt', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-001', 'M0403-011', 'Taśma', 20, 'MTR', 0, 0, '', 1, 0, '');")

        # Kandydat 029-002 — inne kody, te same kategorie.
        c.execute("INSERT INTO bom_technologies VALUES ('029-002', '029-002', 'B', 0, 0, 3, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-002', 'M0105-005', 'Inna tkanina', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-002', 'M0204-005', 'Haczyk', 56, 'szt', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-002', 'M0402-017', 'Inna taśma', 20, 'MTR', 0, 0, '', 1, 0, '');")

        # Kandydat 029-003 — brak BOM (nie wstawiamy do bom_technologies/bom_items).

        conn.commit()
        conn.close()
        yield db_path


# ============================================================================
# Tryb 1: DXF + kod (hybrydowy)
# ============================================================================
def test_similarity_calculation(mock_similarity_db):
    engine = SimilarityEngine(db_path=mock_similarity_db, weight_client=0.4, weight_geom=0.6)
    query_features = DXFFeatures(
        filename="query.dxf",
        bounding_box_width_mm=1000.0,
        bounding_box_height_mm=500.0,
        bounding_box_area_m2=0.5,
        total_cut_length_m=3.0,
        drawing_length_m=0.5,
        contours_count=4,
        aspect_ratio=2.0,
    )
    matches = engine.find_similar(query_code="029-NEW-001", dxf_features=query_features, top_k=3)
    assert len(matches) == 3

    top1 = matches[0]
    assert top1.matched_product_code == "029-001"
    assert top1.client_match is True
    assert top1.similarity_score == 1.0
    assert top1.dxf_distance == 0.0

    match_066 = next(m for m in matches if m.matched_product_code == "066-001")
    assert match_066.client_match is False
    assert abs(match_066.similarity_score - 0.60) < 1e-4


def test_new_client_fallback(mock_similarity_db):
    engine = SimilarityEngine(db_path=mock_similarity_db, weight_client=0.4, weight_geom=0.6)
    query_features = DXFFeatures(
        filename="query.dxf",
        bounding_box_width_mm=1000.0,
        bounding_box_height_mm=500.0,
        bounding_box_area_m2=0.5,
        total_cut_length_m=3.0,
        drawing_length_m=0.5,
        contours_count=4,
        aspect_ratio=2.0,
    )
    matches = engine.find_similar(query_code="999-001", dxf_features=query_features, top_k=3)
    assert matches[0].similarity_score == 1.0


def test_find_similar_neutral_bom_for_missing_candidate():
    """
    Wariant B: kandydat bez BOM (gdy zapytanie ma BOM) dostaje neutralne
    S_bom = 0.5. Wagi NIE są renormalizowane.

    Weryfikujemy formułą: S = (w_klient·1 + w_geom·1 + w_bom·0.5) / Σw.
    Dla defaultów (0.15 / 0.45 / 0.40) i identycznej geometrii:
    S = (0.15 + 0.45 + 0.20) / 1.0 = 0.80.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_neutral.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        c.execute("""
            CREATE TABLE product_dxf_features (
                product_code TEXT PRIMARY KEY, filename TEXT, filenames_json TEXT,
                files_count INTEGER, bounding_box_width_mm REAL, bounding_box_height_mm REAL,
                bounding_box_area_m2 REAL, total_cut_length_m REAL, drawing_length_m REAL,
                contours_count INTEGER, aspect_ratio REAL, layers_json TEXT
            );
        """)
        c.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        # Kandydat z identycznym BOM-em i identyczną geometrią.
        c.execute("INSERT INTO product_profiles VALUES ('029-001', '029', 'Z BOM', 15, 3, 10);")
        c.execute("INSERT INTO product_dxf_features VALUES ('029-001', 'a.dxf', '[\"a.dxf\"]', 1, 1000, 500, 0.5, 3.0, 0.5, 4, 2.0, '[]');")
        c.execute("INSERT INTO bom_technologies VALUES ('029-001', '029-001', 'A', 0, 0, 2, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")

        # Kandydat BEZ BOM, identyczna geometria.
        c.execute("INSERT INTO product_profiles VALUES ('029-002', '029', 'Bez BOM', 20, 3, 12);")
        c.execute("INSERT INTO product_dxf_features VALUES ('029-002', 'b.dxf', '[\"b.dxf\"]', 1, 1000, 500, 0.5, 3.0, 0.5, 4, 2.0, '[]');")

        # Zapytanie ma BOM (bez profilu).
        c.execute("INSERT INTO bom_technologies VALUES ('029-0926-001', '029-0926-001', 'Q', 0, 0, 2, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        conn.commit()
        conn.close()

        engine = SimilarityEngine(db_path=db_path)
        query_features = DXFFeatures(
            filename="q.dxf", bounding_box_width_mm=1000, bounding_box_height_mm=500,
            bounding_box_area_m2=0.5, total_cut_length_m=3.0, drawing_length_m=0.5,
            contours_count=4, aspect_ratio=2.0,
        )
        matches = engine.find_similar("029-0926-001", query_features, top_k=5)
        by_code = {m.matched_product_code: m for m in matches}

        # Kandydat z identycznym BOM-em → 1.0.
        with_bom = by_code["029-001"]
        assert with_bom.bom_used is True
        assert with_bom.similarity_score == pytest.approx(1.0)

        # Kandydat bez BOM → neutralne S_bom w formule, bez własnego BOM.
        without_bom = by_code["029-002"]
        assert without_bom.bom_used is False
        assert without_bom.bom_similarity is None
        assert without_bom.similarity_score == pytest.approx(
            (0.15 * 1.0 + 0.45 * 1.0 + 0.40 * BOM_NEUTRAL_SIMILARITY) / 1.0,
            abs=1e-3,
        )


# ============================================================================
# Parsowanie kodu produktu i dystans miesięcy
# ============================================================================
def test_parse_product_code_valid():
    assert _parse_product_code("029-0926-001") == ("029", 2026, 9)
    assert _parse_product_code("065-1225-002") == ("065", 2025, 12)
    assert _parse_product_code("029-0421-018") == ("029", 2021, 4)
    assert _parse_product_code("999-0123-999") == ("999", 2023, 1)


def test_parse_product_code_invalid_month():
    assert _parse_product_code("029-1326-001") is None  # miesiąc 13
    assert _parse_product_code("029-0026-001") is None  # miesiąc 00


def test_parse_product_code_invalid_format():
    assert _parse_product_code("") is None
    assert _parse_product_code("0290926-001") is None
    assert _parse_product_code("029-0926-") is None
    assert _parse_product_code("abc-defg-hij") is None
    assert _parse_product_code("029-0926-001-x") is None


def test_month_distance():
    assert _month_distance(2026, 9, 2026, 9) == 0
    assert _month_distance(2026, 9, 2026, 6) == 3
    assert _month_distance(2026, 9, 2021, 4) == 65
    assert _month_distance(2021, 4, 2026, 9) == 65


# ============================================================================
# Tryb 2: Tylko kod — ścieżka fallback (data + reliability)
# ============================================================================
def test_find_similar_by_code_filters_client(mock_code_only_db):
    """Do rankingu wchodzą tylko wyroby tego samego klienta."""
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)

    assert len(matches) == 3
    assert all(m.client_code == "029" for m in matches)
    assert all(m.matched_product_code != "065-0926-004" for m in matches)


def test_find_similar_by_code_same_code_is_top1(mock_code_only_db):
    """Identyczny kod (Δmiesięcy=0) → najwyższy wynik."""
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)
    assert matches[0].matched_product_code == "029-0926-001"


def test_find_similar_by_code_date_beats_reliability(mock_code_only_db):
    """
    Bliższa data wygrywa z większą liczbą prób, gdy różnica dat jest duża
    i prób nie ma ekstremalnie wiele. Weryfikujemy że 029-0626-005 (3 mies.
    od zapytania, 2 próby) wyprzedza 029-0421-018 (65 mies., 200 prób).
    """
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)
    codes = [m.matched_product_code for m in matches]
    assert codes.index("029-0626-005") < codes.index("029-0421-018")


def test_find_similar_by_code_returns_dxf_none(mock_code_only_db):
    """Tryb tylko-kod nie zna geometrii — dxf_features=None, dxf_distance=0.0."""
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)
    assert all(m.dxf_features is None for m in matches)
    assert all(m.dxf_distance == 0.0 for m in matches)


def test_find_similar_by_code_fallback_empty(mock_code_only_db):
    """Fallback A: klient bez wyrobów w bazie → pusta lista."""
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="999-0926-001", top_k=10)
    assert matches == []


def test_find_similar_by_code_invalid_query(mock_code_only_db):
    """Nieprawidłowy format kodu → pusta lista (bez wyjątku)."""
    engine = SimilarityEngine(db_path=mock_code_only_db)
    assert engine.find_similar_by_code(query_code="to-nie-kod", top_k=10) == []
    assert engine.find_similar_by_code(query_code="", top_k=10) == []
    assert engine.find_similar_by_code(query_code="029-1326-001", top_k=10) == []


def test_find_similar_by_code_no_db(tmp_path):
    """Brak pliku bazy — pusta lista, bez wyjątku."""
    engine = SimilarityEngine(db_path=tmp_path / "nie_ma.sqlite")
    assert engine.find_similar_by_code(query_code="029-0926-001", top_k=10) == []


# ============================================================================
# Tryb 3: Tylko kod — ścieżka kod + BOM
# ============================================================================
def test_find_similar_by_code_uses_bom_when_available(mock_code_with_bom_db):
    """
    Zapytanie ma BOM → ścieżka kod + BOM. Ranking:
    - 029-001 (identyczny BOM)             → S_bom = 1.0  → S = 1.0
    - 029-003 (bez BOM, neutralne 0.5)     → S ≈ 0.6364
    - 029-002 (inny BOM, struktura ~0.8)   → S < 0.6364

    Kandydat bez BOM wchodzi do rankingu (wariant B) — nie jest wykluczany.
    """
    engine = SimilarityEngine(
        db_path=mock_code_with_bom_db,
        weight_client=0.15,
        weight_bom=0.40,
    )
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)
    codes = [m.matched_product_code for m in matches]

    # Wszyscy kandydaci w rankingu.
    assert "029-001" in codes
    assert "029-002" in codes
    assert "029-003" in codes

    # 029-001 (identyczny BOM) → 029-003 (neutralne) → 029-002 (inny BOM).
    assert codes.index("029-001") < codes.index("029-003") < codes.index("029-002")

    top1 = matches[0]
    assert top1.matched_product_code == "029-001"
    assert top1.bom_used is True
    assert top1.bom_similarity == pytest.approx(1.0)
    assert top1.similarity_score == pytest.approx(1.0)  # (0.15·1 + 0.40·1) / 0.55

    # Kandydat bez BOM — wpisany z neutralnym 0.5, ale bez własnego BOM.
    no_bom = next(m for m in matches if m.matched_product_code == "029-003")
    assert no_bom.bom_used is False
    assert no_bom.bom_similarity is None
    # S = (0.15·1 + 0.40·0.5) / 0.55 = 0.35 / 0.55 ≈ 0.6364
    assert no_bom.similarity_score == pytest.approx(0.6364, abs=1e-3)


def test_find_similar_by_code_falls_back_when_no_query_bom(mock_code_only_db):
    """
    Zapytanie nie ma BOM → fallback do (data + reliability).
    Brak tabel BOM w bazie nie może wywalić silnika.
    """
    engine = SimilarityEngine(db_path=mock_code_only_db)
    matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)
    assert len(matches) > 0
    assert all(m.bom_used is False for m in matches)
    assert all(m.bom_similarity is None for m in matches)


def test_find_similar_by_code_falls_back_when_no_candidate_bom():
    """
    Zapytanie ma BOM, ale ŻADEN kandydat nie ma BOM → fallback do (data + reliability).

    Uwaga 1: kod zapytania (`029-0926-001`) NIE jest wstawiany do `product_profiles`
    — traktujemy go jako nowy kod bez historii MES. Dzięki temu jedynym kandydatem
    w rankingu jest `029-0421-018` (bez BOM-u).

    Uwaga 2: kandydat MUSI mieć poprawny kod w formacie `XXX-YYYY-ZZZ`, bo ścieżka
    fallback parsuje kod regexem i odrzuca nienależące do wzorca (np. `029-001`
    zostałoby pominięte — ma tylko dwie grupy cyfr). `029-0421-018` przechodzi.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "no_cand_bom.sqlite"
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE product_profiles (
                product_code TEXT PRIMARY KEY, client_code TEXT, product_name TEXT,
                total_median_time_min REAL, process_count INTEGER, total_samples INTEGER
            );
        """)
        c.execute("""
            CREATE TABLE bom_technologies (
                product_code TEXT PRIMARY KEY, full_pte_kod TEXT NOT NULL,
                pte_nazwa TEXT, revision INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0, items_count INTEGER NOT NULL DEFAULT 0,
                total_value_pln REAL NOT NULL DEFAULT 0.0, fetched_at TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE bom_items (
                product_code TEXT NOT NULL, ptz_kod TEXT NOT NULL, ptz_nazwa TEXT,
                quantity REAL NOT NULL DEFAULT 0.0, unit TEXT,
                stawka REAL NOT NULL DEFAULT 0.0, wartosc_pln REAL NOT NULL DEFAULT 0.0,
                typ TEXT, twr_typ INTEGER NOT NULL DEFAULT 1,
                is_semiproduct INTEGER NOT NULL DEFAULT 0, fetched_at TEXT NOT NULL,
                PRIMARY KEY (product_code, ptz_kod)
            );
        """)
        # Kandydat — ma profil, BEZ BOM-u, ale z poprawnym kodem XXX-YYYY-ZZZ.
        c.execute("INSERT INTO product_profiles VALUES ('029-0421-018', '029', 'A', 15.0, 3, 10);")
        # Zapytanie — ma BOM, ale NIE ma profilu w product_profiles.
        c.execute("INSERT INTO bom_technologies VALUES ('029-0926-001', '029-0926-001', 'Q', 0, 0, 2, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0107-011', 'T', 30, 'M2', 0, 0, '', 1, 0, '');")
        c.execute("INSERT INTO bom_items VALUES ('029-0926-001', 'M0202-038', 'O', 56, 'szt', 0, 0, '', 1, 0, '');")
        conn.commit()
        conn.close()

        engine = SimilarityEngine(db_path=db_path)
        matches = engine.find_similar_by_code(query_code="029-0926-001", top_k=10)

        # Fallback — kandydat bez BOM jest brany pod uwagę, ale bez składowej BOM.
        assert len(matches) == 1
        assert matches[0].matched_product_code == "029-0421-018"
        assert matches[0].bom_used is False
        assert matches[0].bom_similarity is None