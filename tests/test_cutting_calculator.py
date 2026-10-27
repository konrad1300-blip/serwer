"""Testy jednostkowe dla kalkulatora czasu kroju (ZUND / LECTRA / JIGWEI).

Weryfikują wzór: t_min = (L_mm * mck * mr) / 60,
zgodnie z dokumentacją w docstringu `calculate_cutting_times`.
"""
import pytest

from src.config import FRAME_MULTIPLIER, MACHINE_CUTTING_MULTIPLIERS
from src.processors.cutting_calculator import calculate_cutting_times


def test_returns_all_machines_sorted():
    """Funkcja zwraca wszystkie maszyny z konfiguracji, posortowane alfabetycznie."""
    results = calculate_cutting_times(1000.0)
    names = [r.machine_name for r in results]
    assert names == sorted(MACHINE_CUTTING_MULTIPLIERS.keys())
    assert set(names) == {"ZUND", "LECTRA", "JIGWEI"}


def test_formula_matches_documentation():
    """Wzór dla 10 000 mm zgodny z przykładem z docstringa."""
    results = calculate_cutting_times(10000.0)
    by_name = {r.machine_name: r for r in results}

    expected_zund = round((10000.0 * MACHINE_CUTTING_MULTIPLIERS["ZUND"] * FRAME_MULTIPLIER) / 60.0, 3)
    expected_lectra = round((10000.0 * MACHINE_CUTTING_MULTIPLIERS["LECTRA"] * FRAME_MULTIPLIER) / 60.0, 3)
    expected_jigwei = round((10000.0 * MACHINE_CUTTING_MULTIPLIERS["JIGWEI"] * FRAME_MULTIPLIER) / 60.0, 3)

    assert by_name["ZUND"].cutting_time_min == expected_zund
    assert by_name["LECTRA"].cutting_time_min == expected_lectra
    assert by_name["JIGWEI"].cutting_time_min == expected_jigwei


def test_zero_input_gives_zero_times():
    """Zero mm ścieżki → zero minut na każdej maszynie (nie wyjątek, nie NaN)."""
    results = calculate_cutting_times(0.0)
    assert len(results) == 3
    for r in results:
        assert r.cutting_time_min == 0.0
        assert r.cutting_time_hours == 0.0


def test_hours_property_is_consistent():
    """`cutting_time_hours` zawsze = `cutting_time_min / 60`."""
    results = calculate_cutting_times(10000.0)
    for r in results:
        assert r.cutting_time_hours == pytest.approx(r.cutting_time_min / 60.0)


def test_jigwei_is_slowest():
    """Sanity: JIGWEI ma największy mnożnik → najdłuższy czas."""
    results = calculate_cutting_times(10000.0)
    by_name = {r.machine_name: r for r in results}
    assert by_name["JIGWEI"].cutting_time_min > by_name["LECTRA"].cutting_time_min
    assert by_name["LECTRA"].cutting_time_min > by_name["ZUND"].cutting_time_min