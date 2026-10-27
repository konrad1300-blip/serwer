"""Strona „📦 BOM Wyrobu" (Streamlit).

Przeglądarka BOM (Bill of Materials) dla wyrobów z ERP XL:
- wybór produktu po kodzie / nazwie,
- karta technologii (kod, rewizja, wersja, liczba pozycji, wartość),
- pogrupowana lista materiałów (M01..M15 + kategorie specjalne),
- półprodukty rozwijane w expanderze (bez rekurencji w głąb),
- tabela zbiorcza z sumami per kategoria i grand total.

Dane finansowe (Stawka, Wartość PLN) są ukryte domyślnie. Odblokowanie
hasłem odbywa się w sidebarze (sekcja „🔒 Finanse BOM") i obowiązuje
globalnie w sesji (F5 / restart kasuje).
"""
import sqlite3
from typing import Optional

import pandas as pd
import streamlit as st

from src.config import DB_PATH, has_bom_finance_password
from src.db_metadata import get_metadata
from src.processors.bom_processor import (
    get_all_bom_products,
    get_product_bom,
)


# Etykiety kategorii materiałowych (prefiks 3 znaków kodu PTZ).
CATEGORY_LABELS = {
    "M01": "🧵 Tkaniny powlekane (M01xx)",
    "M02": "🔩 Okucia, oczka, haki (M02xx)",
    "M03": "🔗 Klamry, sprzączki (M03xx)",
    "M04": "🎗️ Taśmy, pasy (M04xx)",
    "M05": "🧵 Zamki, nici, sznurki (M05xx)",
    "M06": "🪢 Gumy, liny, taśmy namiotowe (M06xx)",
    "M07": "🖨️ Folie, nadruki (M07xx)",
    "M08": "🏷️ Etykiety (M08xx)",
    "M09": "🔗 Tulejki, nity, akcesoria (M09xx)",
    "M10": "🧱 Elementy sztywne (HDPE, aluminium) (M10xx)",
    "M11": "🎒 Pasy z klamrą, torby (M11xx)",
    "M12": "🧶 Materiały specjalne (M12xx)",
    "M14": "⚙️ Różne (M14xx)",
    "M15": "💧 Wskaźniki, pochłaniacze (M15xx)",
}

SEMIPRODUCT_LABEL = "🧩 Półprodukty"
OTHER_LABEL = "❓ Pozostałe (nieprzypisane kategorie)"


def _category_for(item) -> str:
    """Zwraca klucz kategorii dla pozycji BOM."""
    if item.is_semiproduct:
        return "SEMI"
    kod = item.ptz_kod or ""
    if len(kod) >= 3 and kod.startswith("M"):
        return kod[:3]
    return "OTHER"


def _category_label(key: str) -> str:
    """Zwraca czytelną etykietę kategorii."""
    if key == "SEMI":
        return SEMIPRODUCT_LABEL
    if key == "OTHER":
        return OTHER_LABEL
    return CATEGORY_LABELS.get(key, f"📦 {key}xx")


def _sort_key(key: str) -> tuple:
    """Sortuje kategorie: najpierw M01..M99, potem SEMI, na końcu OTHER."""
    if key.startswith("M") and len(key) == 3:
        return (0, key)
    if key == "SEMI":
        return (1, "")
    return (2, "")


def _render_refresh_info() -> None:
    """Wyświetla w sidebarze datę ostatniej aktualizacji BOM."""
    ts = get_metadata("last_bom_refresh_at")
    if not ts:
        st.caption("🕐 **Brak historii aktualizacji BOM.**")
        return
    rows = get_metadata("last_bom_refresh_rows") or "?"
    tech = get_metadata("last_bom_refresh_tech") or "?"
    st.success(
        f"🕐 **Ostatnia aktualizacja BOM:** {ts}  \n"
        f"({rows} wierszy → {tech} technologii)"
    )


def _render_items_table(items: list, show_finance: bool = False) -> None:
    """
    Renderuje tabelę pozycji BOM.

    :param items: lista BOMItem.
    :param show_finance: gdy True — dodaje kolumny Stawka [PLN] i Wartość [PLN].
    """
    rows = []
    for it in items:
        row = {
            "Kod": it.ptz_kod,
            "Nazwa": it.ptz_nazwa or "—",
            "Ilość": f"{it.quantity:g}",
            "J.": it.unit or "—",
        }
        if show_finance:
            row["Stawka [PLN]"] = f"{it.stawka:.2f}"
            row["Wartość [PLN]"] = f"{it.wartosc_pln:.2f}"
        rows.append(row)

    if not rows:
        st.info("Brak pozycji.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_semiproduct_expander(
    item, db_path, show_finance: bool = False
) -> None:
    """
    Renderuje expander dla półproduktu z jego własnym BOM-em (jeden poziom
    w głąb — bez rekurencji, żeby uniknąć cykli i przeładowania UI).
    """
    header = f"🧩 {item.ptz_kod} — {item.ptz_nazwa or 'półprodukt'} (ilość: {item.quantity:g} {item.unit})"
    with st.expander(header, expanded=False):
        sub_bom = get_product_bom(item.ptz_kod, db_path=db_path)
        if sub_bom is None:
            st.info(
                f"Brak BOM dla półproduktu `{item.ptz_kod}` w bazie. "
                f"Możliwe, że nie jest produkowany wewnętrznie, albo nie ma go w widoku ERP."
            )
            return

        rev_lbl = f"R{sub_bom.revision:02d}V{sub_bom.version:02d}" if sub_bom.has_revision_suffix else "—"

        if show_finance:
            caption = (
                f"**Technologia:** `{sub_bom.full_pte_kod}`  |  "
                f"Rewizja/wersja: `{rev_lbl}`  |  "
                f"Pozycji: {sub_bom.items_count}  |  "
                f"Wartość: {sub_bom.total_value_pln:.2f} PLN"
            )
        else:
            caption = (
                f"**Technologia:** `{sub_bom.full_pte_kod}`  |  "
                f"Rewizja/wersja: `{rev_lbl}`  |  "
                f"Pozycji: {sub_bom.items_count}"
            )
        st.caption(caption)
        _render_items_table(sub_bom.items, show_finance=show_finance)


def render_bom_page() -> None:
    """Renderuje stronę „📦 BOM Wyrobu"."""
    st.markdown("## 📦 BOM Wyrobu")
    st.caption(
        "Lista materiałów i półproduktów dla wyrobu z widoku ERP "
        "`_im_mm_kalkulacja_Excel`. Zawsze pokazywana jest najnowsza rewizja i wersja technologii."
    )

    if not DB_PATH.exists():
        st.error("Baza SQLite nie istnieje. Pobierz najpierw dane z ERP (📡).")
        return

    # ------------------------------------------------------------------
    # Stan odblokowania finansów w tej sesji.
    # Warunek: hasło skonfigurowane w .env ORAZ odblokowane w tej sesji.
    # Gdy hasła brak — finanse trwale ukryte (bezpieczeństwo domyślne).
    # ------------------------------------------------------------------
    password_configured = has_bom_finance_password()
    show_finance = bool(
        password_configured and st.session_state.get("bom_finance_unlocked", False)
    )

    if not password_configured:
        st.info(
            "🔒 **Dane finansowe BOM (stawki, wartości PLN) są trwale ukryte** — "
            "hasło nieskonfigurowane w `.env` (`BOM_FINANCE_PASSWORD`). "
            "Skontaktuj się z administratorem, jeśli potrzebujesz dostępu."
        )
    elif not show_finance:
        st.info(
            "🔒 **Dane finansowe BOM są ukryte.** Wpisz hasło w pasku bocznym "
            "(sekcja **🔒 Finanse BOM**), aby zobaczyć stawki i wartości PLN."
        )

    products = get_all_bom_products()
    if not products:
        st.warning(
            "Brak danych BOM w bazie. Kliknij **📦 Pobierz BOM z ERP** w pasku bocznym, "
            "żeby wczytać widok `_im_mm_kalkulacja_Excel`."
        )
        _render_refresh_info()
        return

    # --- Wybór produktu ---
    search_kw = st.text_input(
        "Szukaj (kod / nazwa):",
        placeholder="np. 029, Vestas, Plandeka...",
        key="bom_search",
    )

    filtered = products
    if search_kw.strip():
        kw = search_kw.strip().lower()
        filtered = [
            p for p in products
            if kw in p["product_code"].lower()
            or kw in (p["pte_nazwa"] or "").lower()
            or kw in (p["full_pte_kod"] or "").lower()
        ]

    if not filtered:
        st.warning("Brak produktów spełniających kryteria.")
        return

    labels = {}
    for p in filtered:
        name = (p["pte_nazwa"] or "")[:60]
        rev = f"R{p['revision']:02d}V{p['version']:02d}" if (p["revision"] or p["version"]) else "—"
        labels[p["product_code"]] = f"{p['product_code']} | {rev} | {name}"

    selected_code = st.selectbox(
        "Wybierz wyrób:",
        options=list(labels.keys()),
        format_func=lambda c: labels.get(c, c),
        key="bom_product_select",
    )

    if not selected_code:
        return

    bom = get_product_bom(selected_code)
    if not bom:
        st.error(f"Nie znaleziono BOM dla produktu `{selected_code}`.")
        return

    st.divider()

    # --- Karta technologii ---
    rev_lbl = f"R{bom.revision:02d}V{bom.version:02d}" if bom.has_revision_suffix else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kod produktu", bom.product_code)
    c2.metric("Kod technologii", bom.full_pte_kod)
    c3.metric("Rewizja / wersja", rev_lbl)
    c4.metric("Pozycji", bom.items_count)

    if show_finance:
        c5, c6 = st.columns([1, 3])
        c5.metric("Wartość materiałów", f"{bom.total_value_pln:,.2f} PLN")
        with c6:
            st.markdown(f"**Nazwa wyrobu:** {bom.pte_nazwa or '—'}")
    else:
        st.markdown(f"**Nazwa wyrobu:** {bom.pte_nazwa or '—'}")

    st.divider()

    # --- Grupowanie pozycji po kategoriach ---
    grouped: dict = {}
    for it in bom.items:
        key = _category_for(it)
        grouped.setdefault(key, []).append(it)

    sorted_keys = sorted(grouped.keys(), key=_sort_key)

    for key in sorted_keys:
        items = grouped[key]
        label = _category_label(key)
        count = len(items)

        if show_finance:
            subtotal = sum(i.wartosc_pln for i in items)
            header = f"{label} — {count} poz., {subtotal:,.2f} PLN"
        else:
            header = f"{label} — {count} poz."

        with st.expander(header, expanded=False):
            if key == "SEMI":
                # Półprodukty: każdy osobny expander z własnym BOM-em.
                for it in items:
                    _render_semiproduct_expander(it, DB_PATH, show_finance=show_finance)
            else:
                _render_items_table(items, show_finance=show_finance)

    # --- Grand total ---
    st.divider()
    if show_finance:
        st.metric(
            "💰 SUMA WARTOŚCI MATERIAŁÓW",
            f"{bom.total_value_pln:,.2f} PLN",
            f"{bom.items_count} pozycji",
        )
    else:
        st.metric(
            "📦 LICZBA POZYCJI W BOM",
            f"{bom.items_count}",
            help="Wartości finansowe są ukryte — wpisz hasło w pasku bocznym, aby je zobaczyć.",
        )

    # --- Ostatnia aktualizacja ---
    with st.expander("🕐 Informacje o aktualizacji BOM"):
        _render_refresh_info()