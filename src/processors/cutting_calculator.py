"""Kalkulator czasu kroju dla maszyn ZUND, LECTRA, JIGWEI.

Wzór (z kalkulatora v0.15, zachowany 1:1):
    t_min = (L_mm_dxf * mck * mr) / 60

gdzie:
    L_mm_dxf — SUROWA długość ścieżki z pliku DXF (bez korekty skali rysunku),
    mck      — mnożnik czystego kroju dla danej maszyny,
    mr       — mnożnik ramki (FRAME_MULTIPLIER).
"""
from typing import List

from src.config import FRAME_MULTIPLIER, MACHINE_CUTTING_MULTIPLIERS
from src.models import MachineCuttingTime


def calculate_cutting_times(cut_length_dxf_mm: float) -> List[MachineCuttingTime]:
    """
    Wylicza przewidywany czas kroju dla każdej maszyny zdefiniowanej w konfiguracji.

    :param cut_length_dxf_mm: SUROWA długość ścieżki DXF w milimetrach (bez ×10).
    :return: lista MachineCuttingTime, posortowana alfabetycznie po nazwie maszyny.
    """
    results: List[MachineCuttingTime] = []
    for machine_name in sorted(MACHINE_CUTTING_MULTIPLIERS.keys()):
        mck = MACHINE_CUTTING_MULTIPLIERS[machine_name]
        t_min = (cut_length_dxf_mm * mck * FRAME_MULTIPLIER) / 60.0
        results.append(MachineCuttingTime(
            machine_name=machine_name,
            cutting_time_min=round(t_min, 3),
        ))
    return results