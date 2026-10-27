"""Testy jednostkowe dla procesora plików DXF."""
from pathlib import Path
import pytest

from src.config import SAMPLES_DIR
from src.processors.dxf_processor import (
    DXFProcessor,
    extract_product_code_from_filename,
)


def test_extract_product_code_from_filename():
    assert extract_product_code_from_filename("AI029-0421-013.dxf") == "029-0421-013"
    assert extract_product_code_from_filename("AI029-0125-001_1.dxf") == "029-0125-001"
    assert extract_product_code_from_filename("AI055-0821-008_3szt.dxf") == "055-0821-008"
    assert extract_product_code_from_filename("066-1119-010.dxf") == "066-1119-010"


def test_dxf_feature_extraction():
    test_dxf = SAMPLES_DIR / "testowy.dxf"
    assert test_dxf.exists(), "Brak pliku testowy.dxf w data/samples/"

    processor = DXFProcessor()
    features = processor.extract_features(test_dxf)

    assert features.filename == "testowy.dxf"
    assert features.bounding_box_width_mm > 0.0
    assert features.bounding_box_height_mm > 0.0
    assert features.bounding_box_area_m2 > 0.0
    assert features.total_cut_length_m > 0.0
    assert features.contours_count > 0
    assert features.aspect_ratio > 0.0
    assert "CUT" in [l.upper() for l in features.layers_found]


def test_nonexistent_dxf():
    processor = DXFProcessor()
    with pytest.raises(FileNotFoundError):
        processor.extract_features("nieistniejacy_plik_123.dxf")
