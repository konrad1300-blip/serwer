"""Główny punkt wejścia do aplikacji Estymatora Czasów Plandek."""
import argparse
import subprocess
import sys
from pathlib import Path

from src.config import BASE_DIR, DB_PATH, RAW_DATA_PATH
from src.processors.dxf_processor import DXFProcessor, index_dxf_directory_to_db
from src.processors.mes_processor import MESProcessor
from src.processors.similarity_engine import SimilarityEngine
from src.processors.time_estimator import TimeEstimator


def run_streamlit():
    """Uruchamia interfejs graficzny Streamlit."""
    app_path = BASE_DIR / "src" / "ui" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    print(f"🚀 Uruchamianie interfejsu Streamlit: {' '.join(cmd)}")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Zamykanie aplikacji.")


def run_pipeline(kod: str, dxf_path: str, top_k: int = 5, chosen_wzorzec: str = None):
    """Uruchamia pełny potok przetwarzania w trybie konsolowym (CLI)."""
    dxf_file = Path(dxf_path)
    if not dxf_file.exists():
        print(f"❌ Błąd: Plik DXF '{dxf_path}' nie istnieje.")
        sys.exit(1)

    if not DB_PATH.exists():
        print("⚠️ Baza MES nie istnieje. Rozpoczynam automatyczne budowanie bazy...")
        proc = MESProcessor()
        proc.process_and_save()
        index_dxf_directory_to_db()

    print("\n" + "=" * 80)
    print("📐 KROK 1: ANALIZA GEOMETRII DXF")
    print("=" * 80)
    dxf_proc = DXFProcessor()
    features = dxf_proc.extract_features(dxf_file)
    print(f"• Plik:               {features.filename}")
    print(f"• Wymiary gabarytowe: {features.bounding_box_width_mm:.1f} mm x {features.bounding_box_height_mm:.1f} mm")
    print(f"• Pole powierzchni:   {features.bounding_box_area_m2:.3f} m²")
    print(f"• Długość cięcia:     {features.total_cut_length_m:.3f} m")
    print(f"• Długość rysowania:  {features.drawing_length_m:.3f} m")
    print(f"• Proporcja boków:    {features.aspect_ratio:.2f}")

    print("\n" + "=" * 80)
    print("🔍 KROK 2: WYSZUKIWANIE WYROBÓW ANALOGICZNYCH (SIMILARITY ENGINE)")
    print("=" * 80)
    sim_engine = SimilarityEngine(db_path=DB_PATH)
    matches = sim_engine.find_similar(query_code=kod, dxf_features=features, top_k=top_k)

    if not matches:
        print("❌ Nie znaleziono pasujących wyrobów w bazie.")
        sys.exit(1)

    print(f"{'POZ':<4} | {'KOD WYROBU':<15} | {'PODOBIEŃSTWO':<13} | {'KLIENT':<12} | {'NAZWA WYROBU'}")
    print("-" * 80)
    for i, m in enumerate(matches, 1):
        c_match = "Zgodny" if m.client_match else "Inny"
        print(f"{i:<4} | {m.matched_product_code:<15} | {m.similarity_percent:>5.1f}%       | {c_match:<12} | {m.matched_product_name[:35]}")

    ref_code = chosen_wzorzec if chosen_wzorzec else matches[0].matched_product_code

    print("\n" + "=" * 80)
    print(f"⏱️ KROK 3: ESTYMACJA CZASÓW TECHNOLOGICZNYCH (Wzorzec: {ref_code})")
    print("=" * 80)
    estimator = TimeEstimator(db_path=DB_PATH)
    result = estimator.estimate(
        reference_product_code=ref_code,
        target_dxf_features=features,
        target_product_code=kod,
    )

    if result.scaling_factor != 1.0:
        print(f"ℹ️ Zastosowano skalowanie krojenia współczynnikiem: x{result.scaling_factor:.3f}")

    print(f"{'PROCES':<25} | {'SZACOWANY CZAS':<15} | {'ZAKRES Z MES (MIN - MAX)':<25} | {'UWAGI'}")
    print("-" * 80)
    for p in result.processes:
        uwagi = f"Przeskalowano (x{p.scaling_factor})" if p.is_scaled else f"Mediana ({p.sample_count} prób)"
        print(f"{p.process_name:<25} | {p.estimated_time_min:>6.1f} min      | ({p.min_time_min:.1f} – {p.max_time_min:.1f} min)        | {uwagi}")

    print("-" * 80)
    print(f"{'SUMA CZASU / SZTUKA':<25} | {result.total_estimated_time_min:>6.1f} min      | ({result.total_min_time_min:.1f} – {result.total_max_time_min:.1f} min)        | {result.total_estimated_hours:.2f} godz.")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Estymator Czasów Technologicznych Plandek (DXF + MES).")
    parser.add_argument("--ui", action="store_true", help="Uruchom interfejs graficzny Streamlit.")
    parser.add_argument("--kod", type=str, default=None, help="Nowy kod produktu.")
    parser.add_argument("--dxf", type=str, default=None, help="Ścieżka do pliku DXF.")
    parser.add_argument("--top", type=int, default=5, help="Liczba wyrobów w rankingu podobieństwa.")
    parser.add_argument("--wzorzec", type=str, default=None, help="Wymuszenie konkretnego kodu wzorca.")
    parser.add_argument("--rebuild-db", action="store_true", help="Przebuduj bazę SQLite i zaindeksuj pliki DXF.")

    args = parser.parse_args()

    if args.rebuild_db:
        print("🔄 Przebudowa bazy danych MES...")
        proc = MESProcessor()
        proc.process_and_save()
        index_dxf_directory_to_db()
        return

    if args.kod and args.dxf:
        run_pipeline(kod=args.kod, dxf_path=args.dxf, top_k=args.top, chosen_wzorzec=args.wzorzec)
    else:
        # Domyślnie lub z flagą --ui odpalamy interfejs graficzny
        run_streamlit()


if __name__ == "__main__":
    main()