"""Strona „⚖️ Porównywarka Wyrobów" (Streamlit).

Zestawienie grupy wyrobów (A) z pojedynczym wyrobem (B):
- Grupa A: multi-select wyrobów; dla każdego procesu liczymy medianę z median
  wyrobów w grupie (każdy wyrób równo ważony), oraz P25/P50/P75 z tych median,
- Wyrób B: pojedynczy wybór,
- geometria DXF: mediana grupy A vs. wartości B + Δ/Δ% + ostrzeżenie o rozrzucie,
- procesy: mediana grupy A vs. mediana B + Δ/Δ% + drill-down per wyrób grupy,
- analiza ZP: drill-down do wybranego członka grupy A vs. B (wspólny wybór procesu).
"""
from statistics import median
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.config import DB_PATH, to_real_m, to_real_m2, to_real_mm
from src.processors.dxf_processor import get_product_dxf_features
from src.processors.mes_processor import get_product_profile
from src.ui.helpers import find_products, render_zp_table


# Próg |Δ%| powyżej którego kolorujemy komórkę (czerwone dla wzrostu, zielone dla spadku).
DELTA_THRESHOLD_PCT: float = 20.0

# Próg rozrzutu geometrycznego grupy — powyżej ostrzegamy użytkownika.
GEOMETRY_SPREAD_WARN_PCT: float = 50.0

# Limit wyrobów w liście wyszukiwania.
PRODUCT_SEARCH_LIMIT: int = 500


# ==============================================================================
# POMOCNICZE — statystyki
# ==============================================================================
def _percentiles(values: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Zwraca (P25, P50, P75) z listy wartości (interpolacja liniowa jak w pandas).

    - pusta lista → (None, None, None),
    - jedna wartość → (v, v, v).
    """
    if not values:
        return None, None, None
    if len(values) == 1:
        v = float(values[0])
        return v, v, v

    s = sorted(float(v) for v in values)

    def _pct(p: float) -> float:
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        if f == c:
            return s[f]
        return s[f] + (s[c] - s[f]) * (k - f)

    return _pct(0.25), _pct(0.50), _pct(0.75)


def _spread_pct(values: List[float]) -> Optional[float]:
    """Rozrzut (max − min) / mediana × 100 [%] lub None gdy nie da się policzyć."""
    if not values:
        return None
    med = median(values)
    if med == 0:
        return None
    return (max(values) - min(values)) / med * 100.0


# ==============================================================================
# POMOCNICZE — UI
# ==============================================================================
def _color_delta_pct(val) -> str:
    """CSS dla komórki Δ%: czerwone tło powyżej +próg, zielone poniżej −próg."""
    if pd.isna(val):
        return ""
    if val > DELTA_THRESHOLD_PCT:
        return "background-color: #ffe0e0"
    if val < -DELTA_THRESHOLD_PCT:
        return "background-color: #e0ffe0"
    return ""


def _product_label(row: pd.Series) -> str:
    """Czytelna etykieta wyrobu dla selectboxa / multiselecta."""
    name = (row["product_name"] or "")[:50]
    return f"{row['product_code']} | {row['client_code']} | {name}"


def _force_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Wymusza dtype float64 na wskazanych kolumnach (None → NaN)."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _metric_delta(
    va: Optional[float], vb: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    """Zwraca (delta, delta_pct) — delta_pct może być None gdy va == 0 lub brak danych."""
    if va is None or vb is None:
        return None, None
    delta = vb - va
    delta_pct = (delta / va * 100.0) if va != 0 else None
    return round(delta, 3), (round(delta_pct, 1) if delta_pct is not None else None)


# ==============================================================================
# SELEKCJA WYROBÓW
# ==============================================================================
def _select_group_column(label: str, key_prefix: str) -> List[str]:
    """Renderuje kolumnę wyboru GRUPY wyrobów (multiselect z wyszukiwarką)."""
    st.markdown(f"##### {label}")
    search_kw = st.text_input(
        "Szukaj (kod / nazwa / klient):",
        key=f"{key_prefix}_search",
        placeholder="np. 029, Alubag, Plandeka...",
    )

    df = find_products(search_kw, limit=PRODUCT_SEARCH_LIMIT)
    if df.empty:
        st.warning("Brak wyrobów spełniających kryteria.")
        return []

    labels = {row["product_code"]: _product_label(row) for _, row in df.iterrows()}
    options = list(labels.keys())

    selected = st.multiselect(
        "Wybierz wyroby (możesz kilka):",
        options=options,
        format_func=lambda c: labels.get(c, c),
        key=f"{key_prefix}_multi",
        help=(
            "Grupa wyrobów traktowana jest jako jedna „reprezentacja” — dla każdego "
            "procesu liczymy medianę z median wyrobów w grupie (każdy wyrób równo ważony)."
        ),
    )
    return selected or []

def _select_single_column(label: str, key_prefix: str) -> Optional[str]:
    """Renderuje kolumnę wyboru POJEDYNCZEGO wyrobu (selectbox)."""
    st.markdown(f"##### {label}")
    search_kw = st.text_input(
        "Szukaj (kod / nazwa / klient):",
        key=f"{key_prefix}_search",
        placeholder="np. 029, Alubag, Plandeka...",
    )

    df = find_products(search_kw, limit=PRODUCT_SEARCH_LIMIT)
    if df.empty:
        st.warning("Brak wyrobów spełniających kryteria.")
        return None

    labels = {row["product_code"]: _product_label(row) for _, row in df.iterrows()}
    options = list(labels.keys())

    return st.selectbox(
        "Wybierz wyrób:",
        options=options,
        format_func=lambda c: labels.get(c, c),
        key=f"{key_prefix}_select",
    )


# ==============================================================================
# AGREGACJA GRUPY
# ==============================================================================
def _aggregate_group_processes(profiles: list) -> Dict[str, dict]:
    """
    Buduje statystyki procesów dla grupy wyrobów.

    Dla każdego procesu z unii procesów grupy:
    - mediana grupy = mediana z median wyrobów mających ten proces (wariant A,
      każdy wyrób równo ważony),
    - P25/P50/P75 grupy = percentyle z median wyrobów w grupie (P50 == mediana),
    - per_product = {kod_wyrobu: mediana} — do drill-down.

    Zwraca dict: {process_code: {"name", "median", "p25", "p75", "samples", "per_product"}}.
    """
    # Zbierz procesy per wyrób: {code: {pcode: {"median", "samples", "name"}}}
    per_product: Dict[str, Dict[str, dict]] = {}
    for prof in profiles:
        per_product[prof.product_code] = {}
        for pcode, pstat in prof.processes.items():
            per_product[prof.product_code][pcode] = {
                "median": pstat.median_time_per_unit_min,
                "samples": pstat.sample_count,
                "name": pstat.process_name,
            }

    all_pcodes = set()
    for d in per_product.values():
        all_pcodes.update(d.keys())

    result: Dict[str, dict] = {}
    for pcode in all_pcodes:
        medians: List[float] = []
        samples_total = 0
        name = pcode
        per_product_medians: Dict[str, float] = {}

        for code, processes in per_product.items():
            if pcode in processes:
                medians.append(processes[pcode]["median"])
                samples_total += processes[pcode]["samples"]
                name = processes[pcode]["name"]
                per_product_medians[code] = processes[pcode]["median"]

        if not medians:
            continue

        p25, p50, p75 = _percentiles(medians)
        result[pcode] = {
            "name": name,
            "median": p50,
            "p25": p25,
            "p75": p75,
            "samples": samples_total,
            "per_product": per_product_medians,
        }
    return result


def _aggregate_group_geometry(dxf_map: Dict[str, object]) -> Dict[str, dict]:
    """
    Buduje statystyki geometrii grupy.

    Zwraca dict: {attr_name: {"median", "min", "max", "values"}}.
    """
    if not dxf_map:
        return {}

    attrs = [
        "bounding_box_width_mm",
        "bounding_box_height_mm",
        "bounding_box_area_m2",
        "total_cut_length_m",
        "drawing_length_m",
        "contours_count",
        "aspect_ratio",
        "files_count",
    ]
    result = {}
    for attr in attrs:
        values = [float(getattr(f, attr)) for f in dxf_map.values()]
        result[attr] = {
            "median": median(values),
            "min": min(values),
            "max": max(values),
            "values": values,
        }
    return result


# ==============================================================================
# SEKCJA 1: GEOMETRIA DXF
# ==============================================================================
def _render_geometry_section(code_b: str, group_dxf_map: Dict, dxf_b) -> None:
    st.markdown("### 📐 Geometria DXF (wartości rzeczywiste, skala 1:10)")

    if not group_dxf_map and not dxf_b:
        st.info("Żaden z porównywanych wyrobów nie ma zaindeksowanej geometrii DXF.")
        return
    if not group_dxf_map:
        st.warning("Żaden wyrób z grupy A nie ma zaindeksowanej geometrii DXF.")
        return
    if not dxf_b:
        st.warning(f"Wyrób B (`{code_b}`) nie ma zaindeksowanej geometrii DXF.")
        return

    group_geo = _aggregate_group_geometry(group_dxf_map)

    metrics = [
        ("Wymiar X [mm rzecz.]", "bounding_box_width_mm", to_real_mm),
        ("Wymiar Y [mm rzecz.]", "bounding_box_height_mm", to_real_mm),
        ("Pole otaczające [m² rzecz.]", "bounding_box_area_m2", to_real_m2),
        ("Długość cięcia [m rzecz.]", "total_cut_length_m", to_real_m),
        ("Długość rysowania [m rzecz.]", "drawing_length_m", to_real_m),
        ("Liczba konturów", "contours_count", float),
        ("Proporcja boków", "aspect_ratio", float),
        ("Liczba plików DXF", "files_count", float),
    ]

    rows = []
    spread_warnings = []

    for label, attr, converter in metrics:
        values = group_geo[attr]["values"]
        med_raw = group_geo[attr]["median"]
        va = converter(med_raw)
        vb = converter(getattr(dxf_b, attr))

        delta, delta_pct = _metric_delta(va, vb)
        rows.append({
            "Parametr": label,
            "A (mediana grupy)": round(va, 3),
            "B": round(vb, 3),
            "Δ (B − A)": delta,
            "Δ %": delta_pct,
        })

        spread = _spread_pct(values)
        if spread is not None and spread > GEOMETRY_SPREAD_WARN_PCT:
            spread_warnings.append((label, spread))

    df = pd.DataFrame(rows)
    df = _force_numeric(df, ["A (mediana grupy)", "B", "Δ (B − A)", "Δ %"])

    styled = (
        df.style
        .format(
            {
                "A (mediana grupy)": "{:.2f}",
                "B": "{:.2f}",
                "Δ (B − A)": "{:+.2f}",
                "Δ %": "{:+.1f}%",
            },
            na_rep="---",
        )
        .map(_color_delta_pct, subset=["Δ %"])
    )
    st.dataframe(styled, hide_index=True, width="stretch")

    if spread_warnings:
        names = ", ".join(f"{lbl} (rozrzut {s:.0f}%)" for lbl, s in spread_warnings)
        st.warning(
            f"⚠️ **Grupa A jest geometrycznie niejednorodna** — dla następujących metryk "
            f"rozrzut (max − min) / mediana przekracza {GEOMETRY_SPREAD_WARN_PCT:.0f}%: {names}. "
            f"Mediana grupy może nie reprezentować dobrze żadnego konkretnego wyrobu. "
            f"Rozważ zawężenie grupy lub drill-down do konkretnego wyrobu w analizie ZP."
        )

    total_files = sum(int(f.files_count) for f in group_dxf_map.values())
    if total_files > len(group_dxf_map):
        st.caption(
            f"ℹ️ Grupa A zawiera {len(group_dxf_map)} wyrobów, łącznie {total_files} plików DXF "
            f"(wyroby wielomateriałowe mają zsumowane długości cięcia)."
        )


# ==============================================================================
# SEKCJA 2: PROCESY TECHNOLOGICZNE
# ==============================================================================
def _render_processes_section(
    code_b: str, group_profiles: list, profile_b
) -> None:
    st.markdown("### ⏱️ Procesy Technologiczne")

    group_stats = _aggregate_group_processes(group_profiles)

    b_pcodes = set(profile_b.processes.keys()) if profile_b else set()
    all_pcodes = sorted(set(group_stats.keys()) | b_pcodes)

    if not all_pcodes:
        st.info("Żaden z porównywanych wyrobów nie ma zarejestrowanych procesów.")
        return

    rows = []
    drill_rows = []
    only_a: List[str] = []
    only_b: List[str] = []

    for pcode in all_pcodes:
        a_stat = group_stats.get(pcode)
        b_stat = profile_b.processes.get(pcode) if profile_b else None

        a_name = a_stat["name"] if a_stat else (b_stat.process_name if b_stat else pcode)
        b_name = b_stat.process_name if b_stat else None

        a_median = a_stat["median"] if a_stat else None
        b_median = b_stat.median_time_per_unit_min if b_stat else None

        delta, delta_pct = _metric_delta(a_median, b_median)

        rows.append({
            "Proces": a_name,
            "A: Mediana grupy [min]": a_median,
            "A: Próby": a_stat["samples"] if a_stat else None,
            "A: Wyrobów": len(a_stat["per_product"]) if a_stat else None,
            "B: Mediana [min]": b_median,
            "B: Próby": b_stat.sample_count if b_stat else None,
            "Δ (B − A) [min]": delta,
            "Δ %": delta_pct,
        })

        if a_stat and not b_stat:
            only_a.append(a_name)
        if b_stat and not a_stat:
            only_b.append(b_name or pcode)

        # Drill-down per wyrób grupy A
        if a_stat:
            for code, val in a_stat["per_product"].items():
                drill_rows.append({
                    "Proces": a_name,
                    "Wyrób": code,
                    "Źródło": "A (grupa)",
                    "Mediana [min]": val,
                })
        if b_stat:
            drill_rows.append({
                "Proces": b_name or pcode,
                "Wyrób": code_b,
                "Źródło": "B",
                "Mediana [min]": b_stat.median_time_per_unit_min,
            })

    df = pd.DataFrame(rows)
    df = _force_numeric(
        df,
        ["A: Mediana grupy [min]", "B: Mediana [min]", "Δ (B − A) [min]", "Δ %"],
    )

    styled = (
        df.style
        .format(
            {
                "A: Mediana grupy [min]": "{:.2f}",
                "B: Mediana [min]": "{:.2f}",
                "Δ (B − A) [min]": "{:+.2f}",
                "Δ %": "{:+.1f}%",
            },
            na_rep="---",
        )
        .map(_color_delta_pct, subset=["Δ %"])
    )
    st.dataframe(styled, hide_index=True, width="stretch")

    if drill_rows:
        with st.expander("🔍 Mediany per wyrób (drill-down grupy A + wyrób B)"):
            df_drill = pd.DataFrame(drill_rows)
            df_drill = _force_numeric(df_drill, ["Mediana [min]"])
            styled_drill = (
                df_drill.style.format(
                    {"Mediana [min]": "{:.2f}"},
                    subset=["Mediana [min]"],
                    na_rep="---",
                )
            )
            st.dataframe(styled_drill, hide_index=True, width="stretch")

    # ------------------------------------------------------------------
    # Podsumowanie percentylowe (P25 / P50 / P75) — suma czasów jednostkowych
    # ------------------------------------------------------------------
    st.markdown("##### 📊 Suma czasów jednostkowych — percentyle")

    a_sum_p25 = sum(s["p25"] for s in group_stats.values() if s["p25"] is not None)
    a_sum_p50 = sum(s["median"] for s in group_stats.values() if s["median"] is not None)
    a_sum_p75 = sum(s["p75"] for s in group_stats.values() if s["p75"] is not None)

    if profile_b:
        b_sum_p25 = sum(p.q25_time_per_unit_min for p in profile_b.processes.values())
        b_sum_p50 = sum(p.median_time_per_unit_min for p in profile_b.processes.values())
        b_sum_p75 = sum(p.q75_time_per_unit_min for p in profile_b.processes.values())
    else:
        b_sum_p25 = b_sum_p50 = b_sum_p75 = 0.0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🅰️ Grupa A**")
        st.metric("P25 (suma)", f"{a_sum_p25:.2f} min", f"{a_sum_p25 / 60:.2f} h")
        st.metric("P50 (mediana, suma)", f"{a_sum_p50:.2f} min", f"{a_sum_p50 / 60:.2f} h")
        st.metric("P75 (suma)", f"{a_sum_p75:.2f} min", f"{a_sum_p75 / 60:.2f} h")
    with c2:
        st.markdown(f"**🅱️ Wyrób B** (`{code_b}`)")
        st.metric("P25 (suma)", f"{b_sum_p25:.2f} min", f"{b_sum_p25 / 60:.2f} h")
        st.metric("P50 (mediana, suma)", f"{b_sum_p50:.2f} min", f"{b_sum_p50 / 60:.2f} h")
        st.metric("P75 (suma)", f"{b_sum_p75:.2f} min", f"{b_sum_p75 / 60:.2f} h")
    with c3:
        st.markdown("**Δ (B − A)**")
        for label, av, bv in [
            ("P25", a_sum_p25, b_sum_p25),
            ("P50", a_sum_p50, b_sum_p50),
            ("P75", a_sum_p75, b_sum_p75),
        ]:
            delta = bv - av
            pct = (delta / av * 100.0) if av != 0 else None
            st.metric(
                label,
                f"{delta:+.2f} min",
                f"{pct:+.1f}%" if pct is not None else "---",
            )

    st.caption(
        "💡 **Interpretacja:** P25 = wariant optymistyczny (najszybsze mediany wyrobów "
        "w grupie), P50 = mediana grupy, P75 = wariant ostrożny. Dla wyrobu B — "
        "percentyle z jego rzeczywistych odbić MES."
    )

    if only_a:
        st.warning(f"⚠️ Procesy występujące **tylko u A (grupa)**: {', '.join(only_a)}")
    if only_b:
        st.warning(f"⚠️ Procesy występujące **tylko u B**: {', '.join(only_b)}")


# ==============================================================================
# SEKCJA 3: ANALIZA ZP
# ==============================================================================
def _render_zp_section(
    code_b: str, group_profiles: list, profile_b
) -> None:
    st.markdown("### 🔬 Analiza ZP")

    if not group_profiles:
        st.info("Brak wyrobów w grupie A.")
        return
    if not profile_b:
        st.info("Brak profilu wyrobu B.")
        return

    st.caption(
        "Analiza ZP działa **per wyrób**. Wybierz konkretnego członka grupy A, "
        "którego chcesz porównać z wyrobem B."
    )

    a_labels = {
        prof.product_code: f"{prof.product_code} | {(prof.product_name or '')[:50]}"
        for prof in group_profiles
    }

    a_selected_code = st.selectbox(
        "Wybierz wyrób z grupy A do analizy ZP:",
        options=list(a_labels.keys()),
        format_func=lambda c: a_labels.get(c, c),
        key="cmp_zp_group_member",
    )

    profile_a_selected = next(
        (p for p in group_profiles if p.product_code == a_selected_code),
        None,
    )
    if profile_a_selected is None:
        st.error(f"Nie udało się pobrać profilu wyrobu `{a_selected_code}`.")
        return

    a_pcodes = set(profile_a_selected.processes.keys())
    b_pcodes = set(profile_b.processes.keys())
    all_codes = sorted(a_pcodes | b_pcodes)

    if not all_codes:
        st.info("Brak procesów do analizy.")
        return

    label_to_code: Dict[str, str] = {}
    for pcode in all_codes:
        pa = profile_a_selected.processes.get(pcode)
        pb = profile_b.processes.get(pcode)
        name = (pa or pb).process_name
        label_to_code[name] = pcode

    chosen_label = st.selectbox(
        "Wybierz proces do porównania ZP (wspólny dla A i B):",
        options=sorted(label_to_code.keys()),
        key="cmp_zp_process_select",
    )
    chosen_code = label_to_code[chosen_label]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"##### 🅰️ Grupa A → `{a_selected_code}`")
        if chosen_code in profile_a_selected.processes:
            render_zp_table(a_selected_code, chosen_code, key_prefix="cmp_zp_a")
        else:
            st.info(f"Wyrób `{a_selected_code}` nie ma procesu **{chosen_label}**.")

    with col_b:
        st.markdown(f"##### 🅱️ Wyrób B → `{code_b}`")
        if chosen_code in profile_b.processes:
            render_zp_table(code_b, chosen_code, key_prefix="cmp_zp_b")
        else:
            st.info(f"Wyrób B nie ma procesu **{chosen_label}**.")


# ==============================================================================
# GŁÓWNA FUNKCJA STRONY
# ==============================================================================
def render_comparison_page() -> None:
    """Renderuje stronę porównywarki: grupa wyrobów (A) vs. pojedynczy wyrób (B)."""
    st.markdown("## ⚖️ Porównywarka Wyrobów")
    st.caption(
        "Porównanie **grupy wyrobów** (A) z **pojedynczym wyrobem** (B): geometria DXF, "
        "procesy technologiczne (mediana grupy z median wyrobów), percentyle (P25/P50/P75) "
        "oraz analiza ZP dla wybranego członka grupy."
    )

    if not DB_PATH.exists():
        st.error("Baza SQLite nie istnieje. Użyj **📡 Pobierz z ERP** w pasku bocznym.")
        return

    col_a, col_b = st.columns(2)
    with col_a:
        group_codes = _select_group_column("🅰️ Grupa A (multi-select)", "cmp_a")
    with col_b:
        code_b = _select_single_column("🅱️ Wyrób B", "cmp_b")

    if not group_codes or not code_b:
        st.info(
            "Wybierz co najmniej jeden wyrób w grupie A i jeden wyrób B, aby zobaczyć porównanie."
        )
        return

    if code_b in group_codes:
        st.warning(
            f"⚠️ Wyrób B (`{code_b}`) znajduje się również w grupie A. "
            f"Porównanie może być częściowo trywialne (Δ = 0 dla wspólnych procesów)."
        )

    # Zbierz profile grupy (pomiń brakujące z ostrzeżeniem).
    group_profiles = []
    for c in group_codes:
        prof = get_product_profile(c, db_path=DB_PATH)
        if prof:
            group_profiles.append(prof)
        else:
            st.warning(f"Pominięto `{c}` — brak profilu w bazie MES.")

    if not group_profiles:
        st.error("Nie udało się pobrać żadnego profilu z grupy A.")
        return

    profile_b = get_product_profile(code_b, db_path=DB_PATH)
    if not profile_b:
        st.error(f"Nie udało się pobrać profilu wyrobu B (`{code_b}`).")
        return

    # Zbierz cechy DXF (grupa i B).
    group_dxf_map = {}
    for c in group_codes:
        feat = get_product_dxf_features(c, db_path=DB_PATH)
        if feat:
            group_dxf_map[c] = feat

    dxf_b = get_product_dxf_features(code_b, db_path=DB_PATH)

    # Status grupy.
    st.divider()
    group_stats_preview = _aggregate_group_processes(group_profiles)
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Wyrobów w grupie A", f"{len(group_profiles)}")
    mc2.metric("Procesów w grupie A", f"{len(group_stats_preview)}")
    mc3.metric("Plików DXF w grupie A", f"{sum(int(f.files_count) for f in group_dxf_map.values())}")
    mc4.metric("Wyrób B", code_b)

    st.divider()
    _render_geometry_section(code_b, group_dxf_map, dxf_b)

    st.divider()
    _render_processes_section(code_b, group_profiles, profile_b)

    st.divider()
    _render_zp_section(code_b, group_profiles, profile_b)