"""Współdzielone helpery warstwy UI (Streamlit).

Trzymamy tutaj funkcje używane przez więcej niż jedną stronę aplikacji
(`app.py`, `manual_page.py`, `database_browser_page.py`, `comparison_page.py`).
"""
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from src.config import DB_PATH
from src.processors.mes_processor import get_raw_operations


def get_db_stats() -> dict:
    """
    Zwraca podstawowe statystyki bazy SQLite:
    liczbę produktów, klientów oraz zaindeksowanych plików DXF.

    W razie braku bazy lub błędu zapytania zwraca zera — funkcja nigdy
    nie rzuca wyjątku, żeby UI mógł bezpiecznie wyświetlić metryki.
    """
    if not DB_PATH.exists():
        return {"products": 0, "clients": 0, "dxf_count": 0}
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), COUNT(DISTINCT client_code) FROM product_profiles;")
        prod_count, client_count = c.fetchone()
        try:
            c.execute("SELECT COUNT(*) FROM product_dxf_features;")
            dxf_count = c.fetchone()[0]
        except sqlite3.OperationalError:
            dxf_count = 0
        conn.close()
        return {"products": prod_count, "clients": client_count, "dxf_count": dxf_count}
    except Exception:
        return {"products": 0, "clients": 0, "dxf_count": 0}


def find_products(
    search_kw: str = "",
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Zwraca listę wyrobów do wyboru w UI (selectbox, tabela).

    Filtrowanie: dopasowanie LIKE (substring) na kodzie produktu, nazwie
    wyrobu lub kodzie klienta. W razie braku tabeli `product_dxf_features`
    (świeża baza bez indeksacji) stosuje fallback bez kolumny `ma_dxf`.

    :param search_kw: fraza wyszukiwania (pusta = brak filtra).
    :param limit: maksymalna liczba wierszy.
    :param db_path: ścieżka do bazy; domyślnie `DB_PATH` z configu.
    :return: DataFrame z kolumnami: product_code, client_code, product_name,
             total_median_time_min, process_count, total_samples, ma_dxf.
             Pusty DataFrame gdy baza nie istnieje lub brak dopasowań.
    """
    path = Path(db_path) if db_path else DB_PATH
    if not path.exists():
        return pd.DataFrame()

    safe_limit = max(1, int(limit))
    conn = sqlite3.connect(path)
    try:
        query = f"""
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
        query += f" ORDER BY p.product_code LIMIT {safe_limit};"

        try:
            return pd.read_sql_query(query, conn, params=params)
        except Exception:
            fallback_query = f"""
                SELECT 
                    product_code, client_code, product_name,
                    total_median_time_min, process_count, total_samples,
                    'BRAK ⚠️' AS ma_dxf
                FROM product_profiles
            """
            fb_params = []
            if search_kw.strip():
                fallback_query += " WHERE product_code LIKE ? OR product_name LIKE ? OR client_code LIKE ?"
                kw = f"%{search_kw.strip()}%"
                fb_params.extend([kw, kw, kw])
            fallback_query += f" ORDER BY product_code LIMIT {safe_limit};"
            return pd.read_sql_query(fallback_query, conn, params=fb_params)
    finally:
        conn.close()


def render_zp_table(
    product_code: str,
    process_code: str,
    key_prefix: str,
) -> None:
    """
    Renderuje tabelę surowych odbić ZP dla danego produktu i procesu.

    Zawiera: filtr Dział ZP (multiselect), tabelę ZP-ków z planem i realem
    oraz odchyleniem, oraz zbiorcze metryki (średnia / mediana / min / max
    w jednym rzędzie + suma realna ZP poniżej).

    :param product_code: kod wyrobu.
    :param process_code: kod procesu.
    :param key_prefix: unikalny prefix dla kluczy widgetów Streamlit —
                       pozwala renderować kilka instancji w jednej sesji.
    """
    raw_ops = get_raw_operations(product_code, process_code, db_path=DB_PATH)

    if not raw_ops:
        st.info(f"Brak surowych odbić ZP dla `{product_code}` / `{process_code}`.")
        return

    if all(op.dzial_zp in (None, "") for op in raw_ops):
        st.warning("⚠️ Wszystkie odbicia tego procesu mają **puste pole Dział ZP**.")

    dostepne_dzialy = sorted({op.dzial_zp for op in raw_ops if op.dzial_zp})
    if dostepne_dzialy:
        wybrane_dzialy = st.multiselect(
            "🔎 Filtruj Dział ZP:",
            options=dostepne_dzialy,
            default=dostepne_dzialy,
            key=f"{key_prefix}_dzial_filter",
        )
        raw_ops = [op for op in raw_ops if op.dzial_zp in wybrane_dzialy]

    if not raw_ops:
        st.info("Brak odbić po zastosowaniu filtra.")
        return

    st.caption(f"Znaleziono **{len(raw_ops)}** odbić operacji dla produktu `{product_code}`.")

    rows = []
    for op in raw_ops:
        real = op.real_time_per_unit_min
        planned = op.planned_time_per_unit_min
        planned_total = op.planned_time_total_min

        deviation = None
        if planned and planned > 0:
            deviation = f"{((real - planned) / planned) * 100:+.1f}%"

        real_total_str = (
            f"{real * op.unit_count:.2f}"
            if op.unit_count and op.unit_count > 0
            else "—"
        )

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
        # Mediana z tego samego podzbioru co średnia (> 0), żeby porównanie
        # było spójne — odrzucamy wartości zerowe i ujemne (błędne odbicia).
        real_median = float(pd.Series(real_values).median())

        # Rząd 1: 4 metryki — mieszczą się w połowie szerokości (kolumna w porównywarce).
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Średnia realna", f"{sum(real_values) / len(real_values):.2f} min")
        c2.metric("Mediana realna", f"{real_median:.2f} min")
        c3.metric("Min realna", f"{min(real_values):.2f} min")
        c4.metric("Max realna", f"{max(real_values):.2f} min")

        # Rząd 2: suma realna ZP — pełna szerokość, pod rzędem metryk.
        st.metric(
            "Suma realna (ZP)",
            f"{sum(op.real_time_per_unit_min * (op.unit_count or 0) for op in raw_ops):.2f} min",
        )