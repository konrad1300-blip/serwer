"""Strona „📊 Przeglądarka Bazy MES" (Streamlit).

Eksploracja wyrobów, procesów, geometrii DXF oraz drill-down do odbić ZP-ków
z tabeli `mes_raw_operations`.
"""
import sqlite3
from typing import Dict

import pandas as pd
import streamlit as st

from src.config import DB_PATH, to_real_m, to_real_m2, to_real_mm
from src.processors.cutting_calculator import calculate_cutting_times
from src.processors.dxf_processor import get_product_dxf_features
from src.processors.mes_processor import get_product_profile, get_raw_operations


def _get_plan_median_per_process(
    conn: sqlite3.Connection,
    product_code: str,
) -> Dict[str, float]:
    """
    Zwraca medianę planu [min/szt] per process_code dla wyrobu.

    Mediana liczona wyłącznie z odbić z niezerowym planem (> 0). Rekordy
    z pustym lub zerowym planem są pomijane — inaczej mediana byłaby
    zaniżana przez masowe zera planistyczne.

    :param conn: otwarte połączenie SQLite (współdzielone z resztą strony).
    :param product_code: kod wyrobu.
    :return: dict {process_code: mediana_planu_min_szt}. Brak klucza = brak planu.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT process_code, planned_time_per_unit_min
        FROM mes_raw_operations
        WHERE product_code = ?
          AND planned_time_per_unit_min IS NOT NULL
          AND planned_time_per_unit_min > 0;
    """, (product_code,))
    by_proc: Dict[str, list] = {}
    for proc_code, val in cursor.fetchall():
        by_proc.setdefault(proc_code, []).append(float(val))
    return {pc: float(pd.Series(vals).median()) for pc, vals in by_proc.items()}


def render_database_browser_page():
    """Renderuje stronę przeglądarki bazy MES z drillem do surowych operacji ZP."""
    st.markdown("## 📊 Przeglądarka Bazy Wiedzy MES")
    st.caption("Eksploracja wyrobów, procesów, geometrii DXF oraz analiza odbić ZP-ków.")

    if not DB_PATH.exists():
        st.error("Baza SQLite nie istnieje. Użyj **📡 Pobierz z ERP** w pasku bocznym.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        search_kw = st.text_input("Szukaj wyrobu:", placeholder="np. 029, Alubag, Plandeka...")

        query = """
            SELECT 
                p.product_code, p.client_code, p.product_name,
                p.total_median_time_min, p.process_count, p.total_samples,
                CASE WHEN d.product_code IS NOT NULL THEN 'TAK ✅' ELSE 'BRAK ⚠️' END AS ma_dxf
            FROM product_profiles p
            LEFT JOIN product_dxf_features d ON p.product_code = d.product_code
        """
        params = []
        if search_kw.strip():
            query += " WHERE p.product_code LIKE ? OR p.product_name LIKE ? OR p.client_code LIKE ?"
            kw = f"%{search_kw.strip()}%"
            params.extend([kw, kw, kw])
        query += " ORDER BY p.product_code LIMIT 100;"

        try:
            df_prods = pd.read_sql_query(query, conn, params=params)
        except Exception:
            fallback_query = """
                SELECT 
                    product_code, client_code, product_name,
                    total_median_time_min, process_count, total_samples,
                    'BRAK ⚠️' AS ma_dxf
                FROM product_profiles
            """
            if search_kw.strip():
                fallback_query += " WHERE product_code LIKE ? OR product_name LIKE ? OR client_code LIKE ?"
            fallback_query += " ORDER BY product_code LIMIT 100;"
            df_prods = pd.read_sql_query(fallback_query, conn, params=params)

        def _on_product_row_select():
            state = st.session_state.get("products_table")
            if state is None:
                return
            rows = state.selection.rows
            if not rows:
                return
            idx = rows[0]
            if 0 <= idx < len(df_prods):
                st.session_state["pending_product_code"] = df_prods.iloc[idx]["product_code"]

        st.caption("💡 Kliknij wiersz w tabeli, aby automatycznie wybrać wyrób w profilu szczegółowym poniżej.")
        st.dataframe(
            df_prods.rename(columns={
                "product_code": "Kod Produktu",
                "client_code": "Klient",
                "product_name": "Nazwa Wyrobu",
                "total_median_time_min": "Suma Czasów [min]",
                "process_count": "Liczba Procesów",
                "total_samples": "Liczba Zleceń",
                "ma_dxf": "Geometria DXF",
            }),
            hide_index=True,
            width="stretch",
            on_select=_on_product_row_select,
            selection_mode="single-row",
            key="products_table",
        )

        st.divider()
        st.markdown("### 🔎 Szczegółowy Profil Wyrobu")

        options_list = df_prods["product_code"].tolist() if not df_prods.empty else []
        if not options_list:
            st.warning("Brak wyrobów spełniających kryteria wyszukiwania.")
            return

        target_from_click = st.session_state.pop("pending_product_code", None)
        if target_from_click is not None and target_from_click in options_list:
            st.session_state["selected_code_widget"] = target_from_click
        elif st.session_state.get("selected_code_widget") not in options_list:
            st.session_state["selected_code_widget"] = options_list[0]

        selected_code = st.selectbox(
            "Wybierz wyrób:",
            options=options_list,
            key="selected_code_widget",
        )

        if selected_code:
            profile = get_product_profile(selected_code, db_path=DB_PATH)
            dxf_feat = get_product_dxf_features(selected_code, db_path=DB_PATH)

            # Mediany planu [min/szt] per proces — jednym zapytaniem do raw ops.
            plan_by_proc = _get_plan_median_per_process(conn, selected_code)

            d_col1, d_col2 = st.columns([1.2, 1.0])
            with d_col1:
                st.markdown(f"**Kod:** `{profile.product_code}` | **Klient:** `{profile.client_code}`")
                st.markdown(f"**Nazwa:** {profile.product_name}")

                proc_rows = []
                for p in profile.processes.values():
                    plan_val = plan_by_proc.get(p.process_code)
                    plan_str = f"{plan_val:.2f}" if plan_val is not None else "0.00"
                    proc_rows.append({
                        "Proces": p.process_name,
                        "Mediana [min]": f"{p.median_time_per_unit_min:.2f}",
                        "Plan [min/szt]": plan_str,
                        "P25 [min]": f"{p.q25_time_per_unit_min:.2f}",
                        "P50 [min]": f"{p.q50_time_per_unit_min:.2f}",
                        "P75 [min]": f"{p.q75_time_per_unit_min:.2f}",
                        "Min [min]": f"{p.min_time_per_unit_min:.2f}",
                        "Max [min]": f"{p.max_time_per_unit_min:.2f}",
                        "Próby": p.sample_count,
                        "Mediana [h]": f"{p.median_time_per_unit_min / 60.0:.3f}",
                    })

                if profile.processes:
                    proc_list = list(profile.processes.values())
                    suma_median = sum(p.median_time_per_unit_min for p in proc_list)
                    suma_p25 = sum(p.q25_time_per_unit_min for p in proc_list)
                    suma_p50 = sum(p.q50_time_per_unit_min for p in proc_list)
                    suma_p75 = sum(p.q75_time_per_unit_min for p in proc_list)
                    suma_min = sum(p.min_time_per_unit_min for p in proc_list)
                    suma_max = sum(p.max_time_per_unit_min for p in proc_list)
                    suma_proby = sum(p.sample_count for p in proc_list)
                    suma_plan = sum(plan_by_proc.get(p.process_code, 0.0) for p in proc_list)

                    proc_rows.append({
                        "Proces": "👉 SUMA / SZTUKA",
                        "Mediana [min]": f"{suma_median:.2f}",
                        "Plan [min/szt]": f"{suma_plan:.2f}",
                        "P25 [min]": f"{suma_p25:.2f}",
                        "P50 [min]": f"{suma_p50:.2f}",
                        "P75 [min]": f"{suma_p75:.2f}",
                        "Min [min]": f"{suma_min:.2f}",
                        "Max [min]": f"{suma_max:.2f}",
                        "Próby": suma_proby,
                        "Mediana [h]": f"{suma_median / 60.0:.3f}",
                    })

                st.table(pd.DataFrame(proc_rows))

            with d_col2:
                if dxf_feat:
                    st.markdown("#### 📐 Geometria DXF (rzeczywiste, ×10):")
                    st.metric("Wymiary (rzecz.)",
                              f"{to_real_mm(dxf_feat.bounding_box_width_mm):.1f} x {to_real_mm(dxf_feat.bounding_box_height_mm):.1f} mm")
                    st.metric("Długość cięcia (rzecz.)", f"{to_real_m(dxf_feat.total_cut_length_m):.2f} m")
                    st.metric("Pole (rzecz.)", f"{to_real_m2(dxf_feat.bounding_box_area_m2):.3f} m²")

                    st.markdown("##### ✂️ Przewidywany czas kroju:")
                    for mct in calculate_cutting_times(dxf_feat.total_cut_length_m * 1000.0):
                        st.metric(f"🛠️ {mct.machine_name}",
                                  f"{mct.cutting_time_min:.2f} min",
                                  f"{mct.cutting_time_hours:.3f} h")
                else:
                    st.info("Ten wyrób nie ma zapisanej geometrii DXF.")

            st.divider()
            st.markdown("### 🔬 Analiza ZP-ków dla wybranego procesu")

            if not profile.processes:
                st.info("Ten produkt nie ma zarejestrowanych procesów.")
            else:
                process_options = {
                    f"{p.process_name} ({p.process_code})": p.process_code
                    for p in profile.processes.values()
                }
                chosen_proc_label = st.selectbox(
                    "Wybierz proces do analizy szczegółowej:",
                    options=list(process_options.keys()),
                )
                chosen_proc_code = process_options[chosen_proc_label]
                raw_ops = get_raw_operations(selected_code, chosen_proc_code, db_path=DB_PATH)

                if not raw_ops:
                    st.warning("Brak surowych odbić dla tego procesu.")
                else:
                    brak_dzialu = all(op.dzial_zp in (None, "") for op in raw_ops)
                    if brak_dzialu:
                        st.warning(
                            "⚠️ Wszystkie odbicia tego procesu mają **puste pole Dział ZP**."
                        )

                    dostepne_dzialy = sorted({op.dzial_zp for op in raw_ops if op.dzial_zp})
                    if dostepne_dzialy:
                        wybrane_dzialy = st.multiselect(
                            "🔎 Filtruj Dział ZP:",
                            options=dostepne_dzialy,
                            default=dostepne_dzialy,
                            key=f"dzial_filter_{selected_code}_{chosen_proc_code}",
                        )
                        raw_ops = [op for op in raw_ops if op.dzial_zp in wybrane_dzialy]

                    if raw_ops:
                        st.caption(
                            f"Znaleziono **{len(raw_ops)}** odbić operacji **{chosen_proc_label}** "
                            f"dla produktu `{selected_code}`."
                        )

                        rows = []
                        for op in raw_ops:
                            real = op.real_time_per_unit_min
                            planned = op.planned_time_per_unit_min
                            planned_total = op.planned_time_total_min

                            deviation = None
                            if planned and planned > 0:
                                deviation = f"{((real - planned) / planned) * 100:+.1f}%"

                            if op.unit_count and op.unit_count > 0:
                                real_total_str = f"{real * op.unit_count:.2f}"
                            else:
                                real_total_str = "—"

                            rows.append({
                                "Dział ZP": op.dzial_zp or "—",
                                "ZP": op.zp_number or "—",
                                "ZS": op.zs_number or "—",
                                "Sztuk": op.unit_count if op.unit_count else None,
                                "Plan [min/szt]": f"{planned:.2f}" if planned is not None else "—",
                                "Plan ZP [min]": f"{planned_total:.2f}" if planned_total is not None else "—",
                                "Realny [min/szt]": f"{real:.2f}",
                                "Realny ZP [min]": real_total_str,
                                "Odchylenie": deviation or "—",
                            })

                        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

                        real_values = [op.real_time_per_unit_min for op in raw_ops if op.real_time_per_unit_min > 0]
                        if real_values:
                            # Mediana z tego samego podzbioru co średnia (> 0),
                            # dla spójności porównania.
                            real_median = float(pd.Series(real_values).median())

                            c1, c2, c3, c4, c5 = st.columns(5)
                            c1.metric("Średnia realna", f"{sum(real_values) / len(real_values):.2f} min")
                            c2.metric("Mediana realna", f"{real_median:.2f} min")
                            c3.metric("Min realna", f"{min(real_values):.2f} min")
                            c4.metric("Max realna", f"{max(real_values):.2f} min")
                            c5.metric(
                                "Suma realna (ZP)",
                                f"{sum(op.real_time_per_unit_min * (op.unit_count or 0) for op in raw_ops):.2f} min",
                            )

    finally:
        conn.close()