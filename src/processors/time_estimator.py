"""Moduł estymatora czasów procesów technologicznych (Procesor 4)."""
import argparse
from pathlib import Path
from typing import List, Optional, Union

from src.config import CUTTING_PROCESS_CODES, DB_PATH
from src.models import DXFFeatures, EstimatedProcess, EstimationResult
from src.processors.cutting_calculator import calculate_cutting_times
from src.processors.dxf_processor import DXFProcessor, get_product_dxf_features
from src.processors.mes_processor import get_product_profile


class TimeEstimator:
    """
    Estymuje czasy jednostkowe procesów na podstawie wyrobu wzorcowego
    z uwzględnieniem skalowania operacji cięcia w oparciu o geometrię DXF.
    Dodatkowo wylicza przewidywany czas kroju dla maszyn ZUND/LECTRA/JIGWEI.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH

    def estimate(
        self,
        reference_product_code: str,
        target_dxf_features: Optional[DXFFeatures] = None,
        target_product_code: Optional[str] = None,
    ) -> EstimationResult:
        """Wyznacza przewidywane czasy procesów technologicznych dla wybranego wzorca."""
        ref_profile = get_product_profile(reference_product_code, self.db_path)
        if not ref_profile:
            raise ValueError(f"Nie znaleziono w bazie wzorca o kodzie: '{reference_product_code}'")

        scaling_factor = 1.0
        ref_features = get_product_dxf_features(reference_product_code, self.db_path)

        if target_dxf_features and ref_features:
            if ref_features.total_cut_length_m > 0 and target_dxf_features.total_cut_length_m > 0:
                scaling_factor = target_dxf_features.total_cut_length_m / ref_features.total_cut_length_m

        estimated_processes: List[EstimatedProcess] = []
        total_est = 0.0
        total_min = 0.0
        total_max = 0.0
        total_q25 = 0.0
        total_q50 = 0.0
        total_q75 = 0.0

        sorted_processes = sorted(ref_profile.processes.values(), key=lambda p: p.process_name)

        for p_stat in sorted_processes:
            p_code = p_stat.process_code.upper()
            is_cutting = any(kw in p_code for kw in CUTTING_PROCESS_CODES)

            if is_cutting and abs(scaling_factor - 1.0) > 0.001:
                est_time = p_stat.median_time_per_unit_min * scaling_factor
                min_time = p_stat.min_time_per_unit_min * scaling_factor
                max_time = p_stat.max_time_per_unit_min * scaling_factor
                q25_time = p_stat.q25_time_per_unit_min * scaling_factor
                q50_time = p_stat.q50_time_per_unit_min * scaling_factor
                q75_time = p_stat.q75_time_per_unit_min * scaling_factor
                is_scaled = True
            else:
                est_time = p_stat.median_time_per_unit_min
                min_time = p_stat.min_time_per_unit_min
                max_time = p_stat.max_time_per_unit_min
                q25_time = p_stat.q25_time_per_unit_min
                q50_time = p_stat.q50_time_per_unit_min
                q75_time = p_stat.q75_time_per_unit_min
                is_scaled = False

            estimated_processes.append(EstimatedProcess(
                process_code=p_stat.process_code,
                process_name=p_stat.process_name,
                estimated_time_min=round(est_time, 2),
                min_time_min=round(min_time, 2),
                max_time_min=round(max_time, 2),
                is_scaled=is_scaled,
                scaling_factor=round(scaling_factor, 3) if is_scaled else 1.0,
                sample_count=p_stat.sample_count,
                q25_time_min=round(q25_time, 2),
                q50_time_min=round(q50_time, 2),
                q75_time_min=round(q75_time, 2),
            ))

            total_est += est_time
            total_min += min_time
            total_max += max_time
            total_q25 += q25_time
            total_q50 += q50_time
            total_q75 += q75_time

        # Obliczenie przewidywanego czasu kroju (na podstawie surowej długości DXF target)
        machine_cutting_times = []
        raw_cut_length_dxf_mm = 0.0
        if target_dxf_features is not None:
            raw_cut_length_dxf_mm = target_dxf_features.total_cut_length_m * 1000.0
            machine_cutting_times = calculate_cutting_times(raw_cut_length_dxf_mm)

        return EstimationResult(
            target_product_code=target_product_code or "NOWY_WYRÓB",
            reference_product_code=ref_profile.product_code,
            reference_product_name=ref_profile.product_name,
            scaling_factor=round(scaling_factor, 3),
            processes=estimated_processes,
            total_estimated_time_min=round(total_est, 2),
            total_min_time_min=round(total_min, 2),
            total_max_time_min=round(total_max, 2),
            total_q25_min=round(total_q25, 2),
            total_q50_min=round(total_q50, 2),
            total_q75_min=round(total_q75, 2),
            machine_cutting_times=machine_cutting_times,
            raw_cut_length_dxf_mm=round(raw_cut_length_dxf_mm, 2),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estymator czasów technologicznych.")
    parser.add_argument("--wzorzec", type=str, required=True, help="Kod wyrobu wzorcowego.")
    parser.add_argument("--dxf", type=str, default=None, help="Opcjonalna ścieżka do pliku DXF.")
    parser.add_argument("--kod", type=str, default="NOWY_PRODUKT", help="Nowy kod wyrobu.")
    args = parser.parse_args()

    target_features = None
    if args.dxf:
        dxf_proc = DXFProcessor()
        target_features = dxf_proc.extract_features(args.dxf)

    estimator = TimeEstimator()
    result = estimator.estimate(
        reference_product_code=args.wzorzec,
        target_dxf_features=target_features,
        target_product_code=args.kod,
    )

    print("=" * 80)
    print(f"⏱️ ESTYMACJA CZASÓW DLA: {result.target_product_code}")
    print(f"   Wzorzec: {result.reference_product_code} ({result.reference_product_name})")
    if result.scaling_factor != 1.0:
        print(f"   Współczynnik skalowania krojenia: {result.scaling_factor:.3f}")
    print("=" * 80)

    for p in result.processes:
        uwagi = f"Przeskalowano (x{p.scaling_factor})" if p.is_scaled else f"Mediana ({p.sample_count} prób)"
        print(f"{p.process_name:<25} | {p.estimated_time_min:>6.1f} min | {uwagi}")

    print("-" * 80)
    print(f"SUMA: {result.total_estimated_time_min:.1f} min ({result.total_estimated_hours:.2f} h)")

    if result.machine_cutting_times:
        print("\n✂️ PRZEWIDYWANY CZAS KROJU (surowe mm DXF: {:.1f}):".format(result.raw_cut_length_dxf_mm))
        for mct in result.machine_cutting_times:
            print(f"   • {mct.machine_name:<8}: {mct.cutting_time_min:.2f} min ({mct.cutting_time_hours:.3f} h)")
    print("=" * 80)