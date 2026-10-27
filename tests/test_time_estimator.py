"""Testy jednostkowe dla estymatora czasów procesów."""
import sqlite3
import tempfile
from pathlib import Path
import pytest

from src.models import DXFFeatures
from src.processors.time_estimator import TimeEstimator


@pytest.fixture
def mock_estimator_db():
    """Tworzy tymczasową bazę z profilem wzorcowym (nowy schemat + percentyle)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_est.sqlite"
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
            CREATE TABLE mes_process_stats (
                product_code TEXT,
                process_code TEXT,
                process_name TEXT,
                product_name TEXT,
                client_code TEXT,
                median_time_min REAL,
                q25_time_min REAL,
                q50_time_min REAL,
                q75_time_min REAL,
                min_time_min REAL,
                max_time_min REAL,
                sample_count INTEGER,
                PRIMARY KEY (product_code, process_code)
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

        c.execute("INSERT INTO product_profiles VALUES ('029-WZORZEC', '029', 'Wzorzec', 20.0, 3, 10);")
        # (product, process, name, product_name, client, median, q25, q50, q75, min, max, count)
        c.execute("INSERT INTO mes_process_stats VALUES ('029-WZORZEC', 'KROJENIE', 'Krojenie', 'Wzorzec', '029', 2.0, 1.5, 2.0, 2.5, 1.0, 3.0, 5);")
        c.execute("INSERT INTO mes_process_stats VALUES ('029-WZORZEC', 'ZGRZEWANIE', 'Zgrzewanie', 'Wzorzec', '029', 10.0, 9.0, 10.0, 11.0, 8.0, 12.0, 5);")
        c.execute("INSERT INTO mes_process_stats VALUES ('029-WZORZEC', 'PAKOWANIE', 'Pakowanie', 'Wzorzec', '029', 1.0, 0.9, 1.0, 1.1, 0.8, 1.2, 5);")

        c.execute("INSERT INTO product_dxf_features VALUES ('029-WZORZEC', 'wzorzec.dxf', '[\"wzorzec.dxf\"]', 1, 1000.0, 500.0, 0.5, 2.0, 0.0, 2, 2.0, '[]');")

        conn.commit()
        conn.close()
        yield db_path


def test_time_estimation_without_dxf(mock_estimator_db):
    estimator = TimeEstimator(db_path=mock_estimator_db)
    result = estimator.estimate(reference_product_code="029-WZORZEC", target_product_code="029-NOWY")

    assert result.reference_product_code == "029-WZORZEC"
    assert result.scaling_factor == 1.0
    assert result.total_estimated_time_min == 13.0
    assert result.total_min_time_min == 9.8
    assert result.total_max_time_min == 16.2


def test_time_estimation_with_dxf_scaling(mock_estimator_db):
    estimator = TimeEstimator(db_path=mock_estimator_db)
    target_features = DXFFeatures(
        filename="nowy.dxf",
        bounding_box_width_mm=2000.0,
        bounding_box_height_mm=1000.0,
        bounding_box_area_m2=2.0,
        total_cut_length_m=4.0,
        drawing_length_m=0.0,
        contours_count=2,
        aspect_ratio=2.0,
    )

    result = estimator.estimate(
        reference_product_code="029-WZORZEC",
        target_dxf_features=target_features,
        target_product_code="029-NOWY",
    )

    assert result.scaling_factor == 2.0

    krojenie = next(p for p in result.processes if p.process_code == "KROJENIE")
    assert krojenie.is_scaled is True
    assert krojenie.estimated_time_min == 4.0
    # Percentyle skalowane razem z medianą
    assert krojenie.q25_time_min == 3.0
    assert krojenie.q50_time_min == 4.0
    assert krojenie.q75_time_min == 5.0

    zgrzewanie = next(p for p in result.processes if p.process_code == "ZGRZEWANIE")
    assert zgrzewanie.is_scaled is False
    assert zgrzewanie.estimated_time_min == 10.0

    # Kalkulator kroju: 4000 mm × mck × mr / 60
    assert len(result.machine_cutting_times) == 3
    machines = {m.machine_name for m in result.machine_cutting_times}
    assert machines == {"ZUND", "LECTRA", "JIGWEI"}


def test_invalid_reference(mock_estimator_db):
    estimator = TimeEstimator(db_path=mock_estimator_db)
    with pytest.raises(ValueError):
        estimator.estimate(reference_product_code="BRAK_WZORCA")