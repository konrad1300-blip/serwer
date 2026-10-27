"""Interfejs użytkownika Streamlit: Estymator Czasów Technologicznych Plandek."""
import hashlib
import io
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Streamlit uruchamia ten plik jako skrypt, nie jako moduł pakietu `src.ui`.
# Bez tego zabiegu `from src.config import ...` kończy się ModuleNotFoundError.
# Wstrzykujemy katalog główny projektu (dwa poziomy wyżej niż src/ui/) do
# sys.path zanim zaimportujemy cokolwiek z `src.*`.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd
import streamlit as st

from src.config import (
    BASE_DIR,
    DB_PATH,
    DEFAULT_CUT_LAYERS,
    DRAWING_SCALE,
    DXF_DIR,
    ERP_DATABASE,
    ERP_SERVER,
    ERP_VIEW,
    INCREMENTAL_LOOKBACK_DAYS,
    SAMPLES_DIR,
    WEIGHT_BOM,
    WEIGHT_CLIENT,
    WEIGHT_GEOM,
    has_bom_finance_password,
    has_erp_credentials,
    is_bom_finance_password_valid,
    to_real_m,
    to_real_m2,
    to_real_mm,
)
from src.db_metadata import get_refresh_info
from src.models import MatchResult
from src.processors.bom_processor import BOMProcessor
from src.processors.data_source import (
    DataFrameDataSource,
    ERPDataSource,
)
from src.processors.dxf_processor import (
    DXFProcessor,
    extract_product_code_from_filename,
    index_dxf_directory_to_db,
    is_valid_upload_filename,
)
from src.processors.mes_processor import MESProcessor
from src.processors.similarity_engine import SimilarityEngine
from src.processors.time_estimator import TimeEstimator
from src.ui.bom_page import render_bom_page
from src.ui.comparison_page import render_comparison_page
from src.ui.database_browser_page import render_database_browser_page
from src.ui.helpers import get_db_stats
from src.ui.manual_page import render_manual_page

# Ustawienia strony Streamlit.
# - `initial_sidebar_state="collapsed"` — sidebar domyślnie zwinięty przy
#   starcie i po F5. Użytkownik może go rozwinąć przyciskiem „>”, tak jak teraz.
st.set_page_config(
    page_title="Estymator Czasów Plandek (DXF + MES)",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ==============================================================================
# NAWIGACJA — WSPÓLNA LISTA STRON + SYNCHRONIZACJA GÓRA <-> SIDEBAR
# ==============================================================================
PAGES = [
    "📐 Kalkulator i Estymator Czasów",
    "⚖️ Porównywarka Wyrobów",
    "📦 BOM Wyrobu",
    "📖 Instrukcja Użytkownika",
    "📊 Przeglądarka Bazy MES",
]

# Wspólne źródło prawdy dla obu nawigacji (górnej listwy i sidebar radio).
# Gdy któraś nawigacja zmieni wartość, callback aktualizuje `selected_page`,
# a przy następnym rerunie obie nawigacje odczytają tę samą wartość.
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = PAGES[0]


def _on_top_nav_change() -> None:
    """Callback górnej listwy — ustawia wspólną stronę z widgetu górnej nawigacji."""
    st.session_state["selected_page"] = st.session_state["nav_top_widget"]


def _on_sidebar_nav_change() -> None:
    """Callback sidebar radio — ustawia wspólną stronę z widgetu sidebaru."""
    st.session_state["selected_page"] = st.session_state["nav_sidebar_widget"]


# ==============================================================================
# GÓRNA LISTWA NAWIGACYJNA
# ==============================================================================
# Layout: dwie kolumny [4, 1] — nawigacja pigułkowa po lewej, badge stanu
# bazy po prawej. Tło listwy: lekko szare (#f0f2f6), zaokrąglone rogi, bez
# ramki. Stylowanie realizowane przez CSS z selektorem :has() na markerze
# `<span id="top-nav-bar-anchor">`, dzięki czemu targetowany jest wyłącznie
# kontener listwy (a nie inne kontenery Streamlita na stronie).
with st.container():
    st.markdown(
        '<span id="top-nav-bar-anchor"></span>'
        '<style>'
        # Stylujemy wyłącznie najgłębszy stVerticalBlock zawierający marker.
        # `:has(#top-nav-bar-anchor)` = kandydat (bezpośredni przodek markera).
        # `:not(:has(... #top-nav-bar-anchor))` = wyklucza przodków wyższego
        # rzędu (którzy mają zagnieżdżony kontener z markerem w środku).
        'div[data-testid="stVerticalBlock"]'
        ':has(#top-nav-bar-anchor)'
        ':not(:has(div[data-testid="stVerticalBlock"] #top-nav-bar-anchor)) {'
        '    background-color: #f0f2f6;'
        '    padding: 0.35rem 1rem;'
        '    border-radius: 8px;'
        '    margin-bottom: 0.6rem;'
        '}'
        '</style>',
        unsafe_allow_html=True,
    )

    _col_nav, _col_status = st.columns([4, 1], vertical_alignment="center")

    with _col_nav:
        # Synchronizacja wstecz: przed utworzeniem widgetu ustawiamy jego wartość
        # z `selected_page`, żeby po zmianie w sidebarze górna listwa też się
        # zaktualizowała. Streamlit pozwala na to przed instancją widgetu.
        st.session_state["nav_top_widget"] = st.session_state["selected_page"]
        st.segmented_control(
            "Nawigacja",
            options=PAGES,
            key="nav_top_widget",
            on_change=_on_top_nav_change,
            label_visibility="collapsed",
        )

    with _col_status:
        _stats = get_db_stats()
        if _stats["products"] > 0:
            st.markdown(
                "<div style='text-align: right;'>"
                "<span style='background: #d4edda; color: #155724; "
                "padding: 4px 10px; border-radius: 12px; font-size: 0.85em; "
                "white-space: nowrap;'>"
                f"🟢 {_stats['products']:,} wyrobów"
                "</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='text-align: right;'>"
                "<span style='background: #f8d7da; color: #721c24; "
                "padding: 4px 10px; border-radius: 12px; font-size: 0.85em; "
                "white-space: nowrap;'>"
                "🔴 Baza pusta"
                "</span></div>",
                unsafe_allow_html=True,
            )


# ==============================================================================
# HELPERY
# ==============================================================================
def format_min_hours(minutes: float) -> str:
    """Formatuje minuty jako 'X.X min (Y.YY h)'."""
    return f"{minutes:.1f} min ({minutes / 60.0:.2f} h)"


def format_real_mm(value_mm_dxf: float) -> str:
    """Formatuje rzeczywiste mm (po korekcie skali 1:10)."""
    return f"{to_real_mm(value_mm_dxf):,.1f} mm"


def format_real_m(value_m_dxf: float) -> str:
    """Formatuje rzeczywiste metry (po korekcie skali 1:10)."""
    return f"{to_real_m(value_m_dxf):.2f} m"


def is_valid_product_code(code: str) -> bool:
    """
    Luźna walidacja kodu produktu. Nie wymuszamy dokładnego wzorca
    `XXX-YYYY-ZZZ`, żeby nie blokować nietypowych przypadków — ale odrzucamy
    jednoznaczne literówki: za krótkie, bez myślnika, ze spacjami.
    """
    code = (code or "").strip()
    if len(code) < 5:
        return False
    if "-" not in code:
        return False
    if re.search(r"\s", code):
        return False
    return True


def get_dxf_files_count() -> int:
    """Zwraca liczbę plików .dxf w katalogu dxf/ (0 jeśli katalog nie istnieje)."""
    if not DXF_DIR.exists():
        return 0
    try:
        return sum(1 for f in DXF_DIR.iterdir() if f.suffix.lower() == ".dxf")
    except OSError:
        return 0


def render_refresh_info():
    """Wyświetla w sidebarze datę/godzinę ostatniej aktualizacji bazy MES."""
    info = get_refresh_info()
    ts = info.get("last_refresh_at")
    if not ts:
        st.caption("🕐 **Brak historii aktualizacji bazy MES.**")
        return
    mode = info.get("last_refresh_mode") or "—"
    mode_lbl = {"full": "pełne", "incremental": "przyrostowe"}.get(mode, mode)
    rows = info.get("last_refresh_rows") or "?"
    try:
        dt = datetime.fromisoformat(ts)
        ts_lbl = dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        ts_lbl = ts
    st.success(f"🕐 **Ostatnia aktualizacja:** {ts_lbl}  \n({mode_lbl}, +{rows} wierszy)")


def _sha256_of_file(path: Path, chunk_size: int = 65536) -> str:
    """Liczy SHA-256 zawartości pliku strumieniowo (bez wczytywania całości do RAM)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_dxf_by_hash(target_hash: str) -> Optional[str]:
    """
    Skanuje katalog dxf/ i zwraca nazwę pliku o podanym SHA-256,
    albo None jeśli nie znaleziono. Pomija pliki nie-czytelne.
    """
    if not DXF_DIR.exists():
        return None
    for f in DXF_DIR.iterdir():
        if f.suffix.lower() != ".dxf" or not f.is_file():
            continue
        try:
            if _sha256_of_file(f) == target_hash:
                return f.name
        except OSError:
            continue
    return None


def _save_uploaded_dxf_to_library(source_path: Path, original_name: str) -> Tuple[str, str]:
    """
    Kopiuje wgrany plik DXF do katalogu dxf/ z deduplikacją po SHA-256.

    Zakłada, że nazwa pliku przeszła już walidację `is_valid_upload_filename()`.
    Wywołujący (UI) powinien sprawdzić maskę nazwy PRZED wywołaniem tej funkcji.

    Zwraca krotkę (action, final_name):
    - ('duplicate', <nazwa istniejącego pliku>) — identyczna zawartość już jest,
    - ('added', <nazwa>) — plik skopiowany pod oryginalną nazwą,
    - ('renamed', <nowa nazwa>) — kolizja nazwy z inną zawartością; dodano sufiks _2, _3, …
    """
    DXF_DIR.mkdir(parents=True, exist_ok=True)
    source_hash = _sha256_of_file(source_path)

    existing = _find_dxf_by_hash(source_hash)
    if existing is not None:
        return "duplicate", existing

    base = Path(original_name)
    stem = base.stem or "uploaded"
    suffix = base.suffix if base.suffix else ".dxf"

    target = DXF_DIR / f"{stem}{suffix}"
    counter = 2
    while target.exists():
        target = DXF_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
        if counter > 1000:
            raise RuntimeError(f"Nie można znaleźć wolnej nazwy dla pliku {original_name}")

    shutil.copy2(source_path, target)

    if target.name == original_name:
        return "added", target.name
    return "renamed", target.name


def render_dxf_plot(dxf_path: Path, cut_layers: set):
    """Generuje wykres 2D geometrii z pliku DXF."""
    import ezdxf

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.set_facecolor("#1e1e1e")
        fig.patch.set_facecolor("#1e1e1e")

        entities = list(msp)
        if not entities:
            for l in doc.layouts:
                if l.name != "Model":
                    entities.extend(list(l))

        for e in entities:
            layer = e.dxf.layer.upper() if hasattr(e.dxf, "layer") else "0"
            is_cut = layer in cut_layers
            color = "#ff4b4b" if is_cut else "#1f77b4"
            lw = 1.6 if is_cut else 0.8

            dxftype = e.dxftype()
            if dxftype == "LINE":
                p1 = (e.dxf.start.x, e.dxf.start.y)
                p2 = (e.dxf.end.x, e.dxf.end.y)
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linewidth=lw)
            elif dxftype in ("POLYLINE", "LWPOLYLINE"):
                if dxftype == "POLYLINE":
                    pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                else:
                    pts = [(p[0], p[1]) for p in e.get_points()]
                if pts:
                    if getattr(e, "is_closed", False) or getattr(e, "closed", False):
                        pts.append(pts[0])
                    xs, ys = zip(*pts)
                    ax.plot(xs, ys, color=color, linewidth=lw)
            elif dxftype in ("CIRCLE", "ARC"):
                cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
                circle = plt.Circle((cx, cy), r, color=color, fill=False, linewidth=lw)
                ax.add_patch(circle)

        ax.set_aspect("equal", adjustable="datalim")
        ax.tick_params(colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#444")
        ax.grid(True, linestyle=":", alpha=0.3, color="white")
        ax.set_xlabel("X [mm]", color="white", fontsize=8)
        ax.set_ylabel("Y [mm]", color="white", fontsize=8)
        fig.tight_layout()
        return fig
    except Exception as ex:
        st.warning(f"Nie udało się wygenerować podglądu graficznego: {ex}")
        return None


# ==========================================
# PASEK BOCZNY
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/blueprint.png", width=64)
    st.title("Estymator Plandek")
    st.caption("System automatycznej wyceny i estymacji czasów technologicznych (DXF + MES)")

    # Synchronizacja wstecz: przed utworzeniem radio ustawiamy jego wartość
    # z `selected_page`, żeby po kliknięciu w górną listwę sidebar pokazał
    # aktualną stronę. Streamlit pozwala na to przed instancją widgetu.
    st.session_state["nav_sidebar_widget"] = st.session_state["selected_page"]
    st.radio(
        "Nawigacja po systemie:",
        options=PAGES,
        key="nav_sidebar_widget",
        on_change=_on_sidebar_nav_change,
    )

    st.divider()
    st.subheader("📊 Baza Wiedzy MES")
    stats = get_db_stats()
    c1, c2 = st.columns(2)
    c1.metric("Wyroby MES", f"{stats['products']:,}")
    c2.metric("Klienci", f"{stats['clients']:,}")
    st.metric("Zaindeksowane DXF", f"{stats['dxf_count']:,}")

    if stats["products"] == 0:
        st.warning("⚠️ Baza MES jest pusta. Kliknij **📡 Pobierz z ERP** poniżej.")

    # ========================================================================
    # 🌐 ERP XL — pobieranie danych (MES + BOM)
    # ========================================================================
    st.divider()
    st.subheader("🌐 Źródło danych ERP XL")
    st.caption(f"MES: `{ERP_VIEW}`  \n`{ERP_SERVER}/{ERP_DATABASE}`")

    render_refresh_info()

    if not has_erp_credentials():
        st.warning(
            "⚠️ Brak poświadczeń ERP. Skopiuj `.env.example` → `.env` "
            "i uzupełnij `ERP_UID`, `ERP_PWD`."
        )

    col_erp_a, col_erp_b = st.columns([1.6, 1.0])
    with col_erp_a:
        btn_erp_download = st.button(
            "📡 Pobierz MES z ERP",
            type="primary",
            width="stretch",
            disabled=not has_erp_credentials(),
            help="Pobiera najnowsze dane MES z ERP XL i zapisuje do bazy SQLite "
                 "(przyrostowo: 90 dni + rekordy niezamknięte).",
        )
    with col_erp_b:
        btn_erp_test = st.button(
            "🔌 Testuj",
            width="stretch",
            disabled=not has_erp_credentials(),
            help="Testuje połączenie z ERP XL.",
        )

    btn_bom_download = st.button(
        "📦 Pobierz BOM z ERP",
        width="stretch",
        disabled=not has_erp_credentials(),
        help="Pobiera pełny widok BOM z ERP XL (zawsze full pull) i zapisuje "
             "do bazy SQLite (tabele bom_technologies, bom_items).",
    )

    if btn_erp_test:
        with st.spinner("Testowanie połączenia z ERP XL..."):
            erp = ERPDataSource()
            ok, msg = erp.test_connection()
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    if btn_erp_download:
        with st.status("📡 Pobieranie danych MES z ERP XL...", expanded=True) as status:
            try:
                proc_pre = MESProcessor()
                mode = "incremental" if proc_pre.has_existing_data() else "full"
                mode_lbl = "przyrostowe (90 dni + rekordy niezamknięte)" if mode == "incremental" else "pełne"
                st.write(f"🔍 Tryb pobierania: **{mode_lbl}**")

                st.write("🔌 Łączenie z bazą ERP XL...")
                erp = ERPDataSource()
                df = erp.load(mode=mode, lookback_days=INCREMENTAL_LOOKBACK_DAYS)
                st.write(f"📥 Pobrano **{len(df):,}** wierszy z widoku `{ERP_VIEW}`.")

                if len(df) == 0:
                    st.write("ℹ️ Brak nowych/zmienionych rekordów — baza pozostaje bez zmian.")
                    status.update(label="✅ Brak zmian do zastosowania", state="complete")
                else:
                    st.write("⚙️ Czyszczenie i agregacja statystyk...")
                    ds = DataFrameDataSource(df, label=f"ERP XL ({mode})")
                    proc = MESProcessor(data_source=ds)
                    proc.process_and_save(mode=mode)
                    st.write("✅ Baza SQLite zaktualizowana.")

                    st.write("📐 Indeksacja plików DXF...")
                    index_dxf_directory_to_db()
                    st.write("✅ Indeksacja DXF zakończona.")

                    status.update(
                        label=f"✅ Dane odświeżone ({mode_lbl}, {len(df):,} wierszy)",
                        state="complete",
                    )
                    st.rerun()
            except Exception as ex:
                status.update(label=f"❌ Błąd pobierania: {ex}", state="error")
                st.warning(
                    "⚠️ **Pracujemy na ostatnio pobranych danych z bazy SQLite.** "
                    "Sprawdź połączenie sieciowe i poświadczenia ERP w pliku `.env`."
                )

    if btn_bom_download:
        with st.status("📦 Pobieranie BOM z ERP XL...", expanded=True) as status:
            try:
                st.write("🔌 Łączenie z bazą ERP XL...")
                proc = BOMProcessor()
                st.write("⚙️ Parsowanie, wybór najnowszych rewizji, agregacja...")
                count = proc.process_and_save()
                if count == 0:
                    status.update(label="⚠️ Brak technologii BOM do zapisania", state="error")
                else:
                    status.update(
                        label=f"✅ BOM zaktualizowany ({count} technologii)",
                        state="complete",
                    )
                    st.rerun()
            except Exception as ex:
                status.update(label=f"❌ Błąd pobierania BOM: {ex}", state="error")

    # ========================================================================
    # 📐 INDEKSACJA DXF
    # ========================================================================
    st.divider()
    st.subheader("📐 Indeksacja DXF")

    dxf_files_count = get_dxf_files_count()
    if DXF_DIR.exists():
        st.caption(f"Plików w `dxf/`: **{dxf_files_count}**")
    else:
        st.caption("⚠️ Katalog `dxf/` nie istnieje.")

    btn_reindex_dxf = st.button(
        "📐 Reindeksuj pliki DXF",
        width="stretch",
        disabled=(dxf_files_count == 0 or not DB_PATH.exists()),
        help="Przelicza cechy geometrii wszystkich plików .dxf z katalogu `dxf/` "
             "i zapisuje je do bazy SQLite. Użyj, gdy dodałeś nowe pliki DXF "
             "bez pełnego pullu z ERP.",
    )

    if dxf_files_count == 0:
        st.caption("ℹ️ Wgraj pliki `.dxf` do katalogu `dxf/` w projekcie.")
    elif not DB_PATH.exists():
        st.caption("ℹ️ Najpierw pobierz dane z ERP (utworzy bazę SQLite).")

    if btn_reindex_dxf:
        with st.status(f"📐 Indeksowanie {dxf_files_count} plików DXF...", expanded=True) as status:
            try:
                st.write(f"📂 Katalog źródłowy: `{DXF_DIR}`")
                st.write("⚙️ Ekstrakcja cech geometrii i zapis do SQLite...")
                indexed_count = index_dxf_directory_to_db()
                st.write(f"✅ Zaindeksowano **{indexed_count}** unikalnych kodów produktu.")
                status.update(
                    label=f"✅ Indeksacja zakończona ({indexed_count} kodów z {dxf_files_count} plików)",
                    state="complete",
                )
                st.rerun()
            except Exception as ex:
                status.update(label=f"❌ Błąd indeksacji: {ex}", state="error")

    # ========================================================================
    # ⚙️ Parametry algorytmu
    # ========================================================================
    st.divider()
    st.subheader("⚙️ Parametry Algorytmu")
    st.caption(
        "Trzy składowe podobieństwa (klient, geometria, BOM) sumują się do **1.0**. "
        "Sterujesz dwoma suwakami — trzeci jest wyliczany."
    )
    st.caption(
        "ℹ️ **F5 / restart przywraca wartości domyślne** suwaków "
        "(`w_klient=0.15`, `w_bom=0.40`, `w_geom=0.45`)."
    )

    w_client = st.slider(
        "Waga kodu klienta (w_klient)",
        min_value=0.0,
        max_value=1.0,
        value=float(WEIGHT_CLIENT),
        step=0.05,
        key="w_client_slider",
        help="Im wyżej, tym większy nacisk na zgodność kodu klienta (pierwsze 3 cyfry).",
    )

    # w_bom ograniczony przez pozostałą pulę — w_geom nie może zejść pod 0.
    w_bom_max = round(1.0 - w_client, 2)
    if "w_bom_slider" in st.session_state:
        if st.session_state["w_bom_slider"] > w_bom_max:
            st.session_state["w_bom_slider"] = w_bom_max

    w_bom = st.slider(
        "Waga struktury BOM (w_bom)",
        min_value=0.0,
        max_value=w_bom_max,
        value=min(float(WEIGHT_BOM), w_bom_max),
        step=0.05,
        key="w_bom_slider",
        help="Im wyżej, tym większy nacisk na zgodność struktury materiałowej BOM. "
             "Działa tylko, gdy zapytanie i kandydat mają BOM w bazie.",
    )

    w_geom = round(1.0 - w_client - w_bom, 2)
    st.metric(
        "Waga cech geometrii (w_geom)",
        f"{w_geom:.2f}",
        help="Automatycznie = 1.0 − w_klient − w_bom. Zmień wartości powyżej, żeby ją skorygować.",
    )

    st.divider()
    st.subheader("✂️ Warstwy Cięcia")
    st.caption("Warstwy traktowane jako linie cięcia/obrysu:")
    cut_layers_str = st.text_input(
        "Warstwy cięcia (po przecinku)",
        value=", ".join(sorted(DEFAULT_CUT_LAYERS)),
    )
    active_cut_layers = {l.strip().upper() for l in cut_layers_str.split(",") if l.strip()}

    # ========================================================================
    # 🔒 FINANSE BOM — odblokowanie danych finansowych hasłem
    # ========================================================================
    st.divider()
    st.subheader("🔒 Finanse BOM")

    if not has_bom_finance_password():
        # Hasło nieskonfigurowane w .env → finanse trwale ukryte (bezpieczeństwo domyślne).
        st.caption(
            "ℹ️ Funkcja niedostępna — hasło nieskonfigurowane w `.env` "
            "(`BOM_FINANCE_PASSWORD`)."
        )
    elif st.session_state.get("bom_finance_unlocked", False):
        st.success("🔓 **Finanse BOM odblokowane** (w tej sesji).")
        if st.button(
            "🔒 Zablokuj finanse BOM",
            width="stretch",
            key="bom_finance_lock_btn",
            help="Ukrywa stawki i wartości PLN na stronie BOM Wyrobu do końca sesji.",
        ):
            st.session_state["bom_finance_unlocked"] = False
            st.rerun()
    else:
        st.caption(
            "Dane finansowe BOM (stawki, wartości PLN) są ukryte. "
            "Wpisz hasło, aby je odblokować w tej sesji."
        )
        # Brak `key=` jest celowy: widget bez klucza nie zapisuje wartości
        # w session_state, więc nie koliduje z próbą czyszczenia po odblokowaniu
        # (Streamlit zabrania modyfikacji klucza widgetu po jego utworzeniu).
        pwd_input = st.text_input(
            "Hasło:",
            type="password",
            label_visibility="collapsed",
            placeholder="Hasło do finansów BOM...",
        )
        if st.button(
            "🔓 Odblokuj",
            type="primary",
            width="stretch",
            key="bom_finance_unlock_btn",
        ):
            if is_bom_finance_password_valid(pwd_input):
                st.session_state["bom_finance_unlocked"] = True
                st.rerun()
            else:
                st.error("❌ Błędne hasło.")


# ==============================================================================
# STRONA 1: KALKULATOR I ESTYMATOR CZASÓW
# ==============================================================================
def render_estimator_page():
    st.markdown("## 📐 Estymator Czasów Technologicznych Plandek")
    st.markdown(
        "Wybierz **tryb wyszukiwania**, wprowadź **kod produktu** (opcjonalnie rysunek **DXF**), "
        "aby dopasować wyroby wzorcowe z historii MES i obliczyć czasy operacji."
    )
    st.caption(f"ℹ️ Rysunki DXF są w skali **1:{int(DRAWING_SCALE)}**. Wymiary i długości poniżej podane są jako **rzeczywiste** (po korekcie skali).")

    if not DB_PATH.exists():
        st.warning(
            "⚠️ **Baza MES jeszcze nie istnieje.** Możesz przeanalizować geometrię DXF, ale bez bazy "
            "nie będzie rankingu podobieństwa ani estymacji czasów. "
            "Użyj **📡 Pobierz MES z ERP** w pasku bocznym."
        )

    st.markdown("### 📥 1. Dane Wejściowe")

    mode_search = st.radio(
        "Tryb wyszukiwania:",
        [
            "📐 DXF + kod (dokładniejszy)",
            "🔢 Tylko kod (bez rysunku)",
        ],
        horizontal=True,
        key="search_mode_radio",
        help="DXF + kod: dopasowanie po geometrii, kodzie klienta i BOM. "
             "Tylko kod: dopasowanie po kliencie + BOM (jeśli dostępny) lub po kliencie + dacie (fallback).",
    )
    mode_dxf = mode_search.startswith("📐")

    if not mode_dxf:
        st.info(
            "🔢 **Tryb bez rysunku DXF.** System najpierw sprawdzi, czy kod zapytania ma BOM. "
            "Jeśli tak — ranking policzy się po **kliencie i BOM-ie** (bez skalowania krojenia). "
            "Jeśli BOM-u brak — fallback do dopasowania po **kliencie i dacie (MMYY) + wiarygodności**."
        )

    selected_dxf_path: Optional[Path] = None
    detected_code_default = "029-0926-001"

    if mode_dxf:
        input_col1, input_col2 = st.columns([1.2, 1.0])
        with input_col1:
            source_type = st.radio(
                "Wybór pliku DXF:",
                ["Wybierz z gotowych próbek", "Prześlij własny plik .DXF"],
                index=1,
                horizontal=True,
            )

            if source_type == "Wybierz z gotowych próbek":
                sample_files = sorted(list(SAMPLES_DIR.glob("*.dxf")))
                sample_names = [f.name for f in sample_files]
                if not sample_names:
                    st.error("Brak plików w katalogu data/samples/!")
                else:
                    default_idx = sample_names.index("testowy.dxf") if "testowy.dxf" in sample_names else 0
                    chosen_sample = st.selectbox("Wybierz plik przykładowy:", sample_names, index=default_idx)
                    if chosen_sample:
                        selected_dxf_path = SAMPLES_DIR / chosen_sample
                        detected_code_default = extract_product_code_from_filename(chosen_sample)
                        if not detected_code_default or len(detected_code_default) < 3:
                            detected_code_default = "029-0926-001"
            else:
                uploaded_file = st.file_uploader("Upuść plik .DXF tutaj:", type=["dxf"])

                save_to_library = st.checkbox(
                    "📥 Dodaj do bazy rysunków (katalog `dxf/`)",
                    value=False,
                    key="save_uploaded_dxf_to_library",
                    help="Po zaznaczeniu plik zostanie trwale skopiowany do katalogu `dxf/`. "
                         "Nazwa pliku musi zaczynać się od maski `AIxxx-xxxx-xxx`. "
                         "Aby zaktualizować bazę SQLite, kliknij **📐 Reindeksuj pliki DXF** w pasku bocznym.",
                )

                if save_to_library and uploaded_file is not None:
                    if is_valid_upload_filename(uploaded_file.name):
                        st.warning(
                            "⚠️ **Plik zostanie trwale zapisany w bazie rysunków** (`dxf/`) "
                            "i uwzględniony przy kolejnej indeksacji DXF. "
                            "Operacja jest odwracalna tylko ręcznie (usunięcie pliku z katalogu + reindeksacja)."
                        )
                    else:
                        st.error(
                            f"❌ **Nazwa pliku nie przechodzi walidacji.**\n\n"
                            f"Plik `{uploaded_file.name}` nie zaczyna się od maski `AIxxx-xxxx-xxx` "
                            f"(np. `AI029-0421-013.dxf`). Plik **NIE zostanie zapisany** do bazy rysunków.\n\n"
                            f"Zmień nazwę pliku (dodaj prefix `AI` + kod produktu) i wgraj ponownie, "
                            f"albo odznacz checkbox, aby użyć tego pliku tylko do bieżącej wyceny."
                        )

                if uploaded_file is not None:
                    temp_dir = Path(tempfile.gettempdir()) / "plandeka_uploads"
                    temp_dir.mkdir(exist_ok=True)
                    temp_file = temp_dir / uploaded_file.name
                    uploaded_bytes = uploaded_file.getbuffer()
                    temp_file.write_bytes(uploaded_bytes)

                    selected_dxf_path = temp_file
                    detected_code_default = extract_product_code_from_filename(uploaded_file.name)
                    if not detected_code_default or len(detected_code_default) < 3:
                        detected_code_default = "029-0926-001"

                    upload_hash = hashlib.sha256(uploaded_bytes).hexdigest()
                    signature = (upload_hash, save_to_library)

                    if st.session_state.get("_dxf_upload_signature") != signature:
                        st.session_state["_dxf_upload_signature"] = signature

                        if save_to_library and is_valid_upload_filename(uploaded_file.name):
                            try:
                                action, final_name = _save_uploaded_dxf_to_library(
                                    temp_file, uploaded_file.name
                                )
                                st.session_state["_dxf_save_result"] = (action, final_name)
                            except Exception as ex:
                                st.session_state["_dxf_save_result"] = ("error", str(ex))
                        else:
                            st.session_state["_dxf_save_result"] = None

                    save_result = st.session_state.get("_dxf_save_result")
                    if save_result:
                        action, payload = save_result
                        if action == "added":
                            st.success(
                                f"✅ Dodano do bazy rysunków: `{payload}`. "
                                f"Kliknij **📐 Reindeksuj pliki DXF** w sidebarze, aby zaktualizować bazę."
                            )
                        elif action == "duplicate":
                            st.info(
                                f"ℹ️ Ten plik już jest w bazie rysunków jako `{payload}` "
                                f"— używam istniejącej kopii."
                            )
                        elif action == "renamed":
                            st.warning(
                                f"⚠️ Plik o tej nazwie już istniał z inną zawartością. "
                                f"Zapisano jako `{payload}`."
                            )
                        elif action == "error":
                            st.error(f"❌ Nie udało się zapisać pliku do bazy rysunków: {payload}")
    else:
        input_col2 = st.container()

    with input_col2:
        new_product_code = st.text_input("Kod produktu (format `XXX-YYYY-ZZZ`):", value=detected_code_default)
        client_code = new_product_code[:3] if len(new_product_code) >= 3 else "???"

        if not is_valid_product_code(new_product_code):
            st.warning(
                "⚠️ Kod produktu wygląda nietypowo. Oczekiwany format: `XXX-YYYY-ZZZ` "
                "(np. `029-0926-001`). Możesz kontynuować, ale dopasowanie po kliencie "
                "będzie mniej wiarygodne."
            )

        is_client_known = False
        if DB_PATH.exists() and len(client_code) == 3:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            try:
                c.execute("SELECT COUNT(*) FROM product_profiles WHERE client_code = ?;", (client_code,))
                is_client_known = (c.fetchone()[0] > 0)
            except sqlite3.OperationalError:
                is_client_known = False
            conn.close()

        if is_client_known:
            st.success(f"↳ **Rozpoznany Klient:** `{client_code}` (Istnieje w bazie MES ✅)")
        else:
            st.warning(f"↳ **Rozpoznany Klient:** `{client_code}` (Nowy klient – dopasowanie po geometrii ⚠️)")

        search_clicked = st.button("🔍 SZUKAJ PODOBNYCH I ESTYMUJ CZASY", type="primary", width="stretch")

    if mode_dxf and selected_dxf_path and selected_dxf_path.exists():
        dxf_proc = DXFProcessor(cut_layers=active_cut_layers)
        try:
            current_features = dxf_proc.extract_features(selected_dxf_path)
            if current_features.contours_count == 0:
                st.warning(
                    "⚠️ **Plik DXF nie zawiera żadnych konturów.** Możliwe przyczyny: "
                    "pusty rysunek, geometria w przestrzeni layoutu (nie model), "
                    "albo niestandardowe nazwy warstw. Sprawdź podgląd 2D i pole **Warstwy cięcia** w pasku bocznym."
                )
                current_features = None
        except Exception as e:
            st.error(f"Błąd analizy pliku DXF: {e}")
            current_features = None
    else:
        current_features = None

    current_signature = (
        "dxf" if mode_dxf else "code",
        str(selected_dxf_path) if selected_dxf_path else None,
        new_product_code,
        w_client,
        w_bom,
        w_geom,
        tuple(sorted(active_cut_layers)),
    )
    if "executed_signature" not in st.session_state:
        st.session_state["executed_signature"] = None

    if mode_dxf:
        can_search = current_features is not None
    else:
        can_search = is_valid_product_code(new_product_code)

    if search_clicked and can_search:
        st.session_state["executed_signature"] = current_signature

    show_results = (
        st.session_state.get("executed_signature") is not None
        and st.session_state["executed_signature"] == current_signature
    )

    if show_results:
        st.divider()
        st.markdown("### 📊 2. Wyniki Analizy i Estymacja Czasów")

        if mode_dxf:
            st.markdown("#### 📐 Cechy Geometryczne z DXF (rzeczywiste, skala 1:10):")
            row1 = st.columns(3)
            row1[0].metric("Wymiar X (rzecz.)", format_real_mm(current_features.bounding_box_width_mm))
            row1[1].metric("Wymiar Y (rzecz.)", format_real_mm(current_features.bounding_box_height_mm))
            row1[2].metric("Pole otaczające (rzecz.)", f"{to_real_m2(current_features.bounding_box_area_m2):.3f} m²")

            row2 = st.columns(3)
            row2[0].metric("Długość cięcia (rzecz.)", format_real_m(current_features.total_cut_length_m))
            row2[1].metric("Długość rysowania (rzecz.)", format_real_m(current_features.drawing_length_m))
            row2[2].metric("Liczba konturów", f"{current_features.contours_count}")

            st.caption(
                f"Proporcje boków: `{current_features.aspect_ratio:.2f}` | "
                f"Wykryte warstwy: `{', '.join(current_features.layers_found)}` | "
                f"Liczba plików dla tego kodu: `{current_features.files_count}`"
            )

            geom_col1, geom_col2 = st.columns([1.0, 1.3])
            with geom_col1:
                st.markdown("##### ✂️ Przewidywany czas kroju (maszyny)")
                raw_cut_mm = current_features.total_cut_length_m * 1000.0
                st.caption(f"Długość ścieżki (surowa z DXF): **{raw_cut_mm:,.1f} mm**")

                from src.processors.cutting_calculator import calculate_cutting_times
                for mct in calculate_cutting_times(raw_cut_mm):
                    st.metric(
                        f"🛠️ {mct.machine_name}",
                        f"{mct.cutting_time_min:.2f} min",
                        f"{mct.cutting_time_hours:.3f} h",
                    )
            with geom_col2:
                with st.expander("🖼️ Podgląd rysunku 2D (DXF)", expanded=True):
                    fig = render_dxf_plot(selected_dxf_path, active_cut_layers)
                    if fig:
                        st.pyplot(fig)
                        plt.close(fig)
        else:
            st.markdown("#### 🔢 Tryb: tylko kod (bez DXF)")
            st.caption(
                "System automatycznie wybrał tryb dopasowania: **kod + BOM** (jeśli oba mają BOM) "
                "lub **kod + data + wiarygodność** (fallback)."
            )

        sim_engine = SimilarityEngine(
            db_path=DB_PATH,
            weight_client=w_client,
            weight_geom=w_geom,
            weight_bom=w_bom,
        )

        if mode_dxf:
            similar_products: List[MatchResult] = sim_engine.find_similar(
                query_code=new_product_code, dxf_features=current_features, top_k=5,
            )
        else:
            similar_products: List[MatchResult] = sim_engine.find_similar_by_code(
                query_code=new_product_code, top_k=5,
            )

        if not similar_products:
            if mode_dxf:
                st.error(
                    "Nie znaleziono wyrobów w bazie danych MES. Możliwe przyczyny: baza jest pusta, "
                    "brak zaindeksowanych plików DXF, albo po prostu brak kandydatów. "
                    "Użyj **📡 Pobierz MES z ERP** w pasku bocznym."
                )
            else:
                st.error(
                    f"Brak wyrobów klienta `{client_code}` w bazie MES. "
                    f"Wycena z historii nie jest możliwa dla tego kodu. "
                    f"Sprawdź kod klienta lub uzupełnij bazę o nowsze zlecenia (📡 Pobierz MES z ERP)."
                )
        else:
            st.markdown("#### 🏆 Ranking Dopasowanych Wyrobów Historycznych:")
            ranking_data = []
            for rank, match in enumerate(similar_products, 1):
                row = {
                    "Poz.": rank,
                    "Kod Wyrobu": match.matched_product_code,
                    "Podobieństwo": f"{match.similarity_percent}%",
                    "Zgodność Klienta": "✅ Zgodny" if match.client_match else "⚠️ Inny",
                    "Nazwa Wyrobu": match.matched_product_name,
                }
                if mode_dxf:
                    ref_feat = match.dxf_features
                    if ref_feat:
                        row["Odległość DXF (d)"] = f"{match.dxf_distance:.3f}"
                        row["Dł. Cięcia (rzecz.)"] = f"{to_real_m(ref_feat.total_cut_length_m):.2f} m"
                        row["Pole (rzecz.)"] = f"{to_real_m2(ref_feat.bounding_box_area_m2):.2f} m²"
                        row["Pliki DXF"] = (
                            f"{ref_feat.files_count} plik(i)" if ref_feat.files_count > 1 else "1 plik"
                        )
                    else:
                        row["Odległość DXF (d)"] = "---"
                        row["Dł. Cięcia (rzecz.)"] = "---"
                        row["Pole (rzecz.)"] = "---"
                        row["Pliki DXF"] = "---"
                ranking_data.append(row)
            st.dataframe(pd.DataFrame(ranking_data), hide_index=True, width="stretch")

            product_options = [
                f"{m.matched_product_code} (Dopasowanie: {m.similarity_percent}%, {m.matched_product_name[:40]})"
                for m in similar_products
            ]
            chosen_option = st.radio(
                "👉 Wybierz wyrób wzorcowy do wyliczenia technologii i czasów:",
                options=product_options, index=0, horizontal=False,
            )
            chosen_code = chosen_option.split(" ")[0]

            if not mode_dxf:
                st.info(
                    "ℹ️ **Estymacja bez korekty geometrycznej.** Czasy opierają się na medianach "
                    "wzorca z MES. Aby uzyskać skalowanie krojenia po długości ścieżki, wróć do trybu "
                    "**📐 DXF + kod** i wgraj rysunek."
                )

            estimator = TimeEstimator(db_path=DB_PATH)
            try:
                est_result = estimator.estimate(
                    reference_product_code=chosen_code,
                    target_dxf_features=current_features,
                    target_product_code=new_product_code,
                )
                st.markdown(f"#### ⏱️ Przewidywane Czasy Procesów Technologicznych (Wzorzec: `{chosen_code}`):")

                if est_result.scaling_factor != 1.0:
                    st.info(
                        f"ℹ️ Czas krojenia został przeskalowany współczynnikiem: **x{est_result.scaling_factor:.3f}** "
                        f"(stosunek długości cięcia: {to_real_m(current_features.total_cut_length_m):.2f} m / wzorzec)."
                    )

                table_rows = []
                for p in est_result.processes:
                    uwagi = f"⚡ Skalowane (x{p.scaling_factor})" if p.is_scaled else f"Mediana ({p.sample_count} prób)"
                    table_rows.append({
                        "Proces": p.process_name,
                        "Szacowany": format_min_hours(p.estimated_time_min),
                        "Percentyl 25": format_min_hours(p.q25_time_min),
                        "Percentyl 50": format_min_hours(p.q50_time_min),
                        "Percentyl 75": format_min_hours(p.q75_time_min),
                        "Zakres MES (Min – Max)": f"({p.min_time_min:.1f} – {p.max_time_min:.1f} min)",
                        "Metoda": uwagi,
                    })
                table_rows.append({
                    "Proces": "👉 SUMA / SZTUKA",
                    "Szacowany": format_min_hours(est_result.total_estimated_time_min),
                    "Percentyl 25": format_min_hours(est_result.total_q25_min),
                    "Percentyl 50": format_min_hours(est_result.total_q50_min),
                    "Percentyl 75": format_min_hours(est_result.total_q75_min),
                    "Zakres MES (Min – Max)": f"({est_result.total_min_time_min:.1f} – {est_result.total_max_time_min:.1f} min)",
                    "Metoda": "Suma jednostkowych operacji",
                })
                st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")

                c_sum1, c_sum2, c_sum3, c_sum4 = st.columns(4)
                c_sum1.metric(
                    "Szacowany czas",
                    f"{est_result.total_estimated_time_min:.1f} min",
                    f"{est_result.total_estimated_hours:.2f} h",
                )
                c_sum2.metric(
                    "Percentyl 25",
                    f"{est_result.total_q25_min:.1f} min",
                    f"{est_result.total_q25_min / 60.0:.2f} h",
                )
                c_sum3.metric(
                    "Percentyl 50 (Mediana)",
                    f"{est_result.total_q50_min:.1f} min",
                    f"{est_result.total_q50_min / 60.0:.2f} h",
                )
                c_sum4.metric(
                    "Percentyl 75",
                    f"{est_result.total_q75_min:.1f} min",
                    f"{est_result.total_q75_min / 60.0:.2f} h",
                )

                st.divider()
                st.markdown("#### 💾 Zapis Karty Technologicznej")
                export_col1, export_col2 = st.columns([1.5, 1.0])

                with export_col1:
                    technologist_notes = st.text_area(
                        "Uwagi technologa / wytyczne produkcyjne:",
                        value=f"Wycena na podstawie analogu {chosen_code}.",
                    )

                with export_col2:
                    geometry_fields = {}
                    if mode_dxf and current_features:
                        geometry_fields = {
                            "plik_dxf": selected_dxf_path.name if selected_dxf_path else None,
                            "wymiary_gabarytowe_mm_rzeczywiste": (
                                f"{to_real_mm(current_features.bounding_box_width_mm):.1f} x "
                                f"{to_real_mm(current_features.bounding_box_height_mm):.1f}"
                            ),
                            "dlugosc_ciecia_m_rzeczywista": round(to_real_m(current_features.total_cut_length_m), 3),
                            "pole_m2_rzeczywiste": round(to_real_m2(current_features.bounding_box_area_m2), 3),
                        }
                    else:
                        geometry_fields = {
                            "plik_dxf": None,
                            "wymiary_gabarytowe_mm_rzeczywiste": None,
                            "dlugosc_ciecia_m_rzeczywista": None,
                            "pole_m2_rzeczywiste": None,
                        }

                    export_data = {
                        "kod_nowy": new_product_code,
                        "kod_klienta": client_code,
                        "tryb_wyszukiwania": "dxf+kod" if mode_dxf else "tylko_kod",
                        **geometry_fields,
                        "wzorzec_kod": est_result.reference_product_code,
                        "wzorzec_nazwa": est_result.reference_product_name,
                        "wspolczynnik_skalowania": est_result.scaling_factor,
                        "calkowity_czas_min": est_result.total_estimated_time_min,
                        "calkowity_czas_godz": round(est_result.total_estimated_hours, 2),
                        "zakres_min_min": est_result.total_min_time_min,
                        "zakres_max_min": est_result.total_max_time_min,
                        "percentyl_25_min": est_result.total_q25_min,
                        "percentyl_50_min": est_result.total_q50_min,
                        "percentyl_75_min": est_result.total_q75_min,
                        "uwagi": technologist_notes,
                        "data_utworzenia": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "krojenie_maszyny": [
                            {"maszyna": m.machine_name, "czas_min": m.cutting_time_min}
                            for m in est_result.machine_cutting_times
                        ],
                        "procesy": [
                            {
                                "proces": p.process_name,
                                "czas_min": p.estimated_time_min,
                                "q25_min": p.q25_time_min,
                                "q50_min": p.q50_time_min,
                                "q75_min": p.q75_time_min,
                                "min_min": p.min_time_min,
                                "max_min": p.max_time_min,
                                "skalowany": p.is_scaled,
                            }
                            for p in est_result.processes
                        ],
                    }
                    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                    st.download_button(
                        label="📥 Pobierz Kartę Technologiczną (JSON)",
                        data=json_str,
                        file_name=f"karta_{new_product_code}_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json", width="stretch",
                    )

                    csv_buffer = io.StringIO()
                    pd.DataFrame(table_rows).to_csv(csv_buffer, index=False)
                    st.download_button(
                        label="📥 Pobierz Zestawienie Czasów (CSV)",
                        data=csv_buffer.getvalue(),
                        file_name=f"czasy_{new_product_code}.csv",
                        mime="text/csv", width="stretch",
                    )

                    if st.button("💾 ZAPISZ KARTĘ NA DYSKU", type="primary", width="stretch"):
                        save_dir = BASE_DIR / "data" / "processed" / "karty_technologiczne"
                        save_dir.mkdir(parents=True, exist_ok=True)
                        target_file = save_dir / f"karta_{new_product_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        target_file.write_text(json_str, encoding="utf-8")
                        st.success(f"Pomyślnie zapisano kartę w: `{target_file.relative_to(BASE_DIR)}`! 🎉")

            except Exception as ex:
                st.error(f"Błąd podczas wyliczania czasów: {ex}")


# ==============================================================================
# ROUTER WIDOKU
# ==============================================================================
_current_page = st.session_state["selected_page"]
if _current_page == "📐 Kalkulator i Estymator Czasów":
    render_estimator_page()
elif _current_page == "⚖️ Porównywarka Wyrobów":
    render_comparison_page()
elif _current_page == "📦 BOM Wyrobu":
    render_bom_page()
elif _current_page == "📖 Instrukcja Użytkownika":
    render_manual_page()
elif _current_page == "📊 Przeglądarka Bazy MES":
    render_database_browser_page()