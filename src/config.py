"""Konfiguracja globalna aplikacji Estymatora Czasów Plandek."""
import os
import secrets
from pathlib import Path
from typing import Dict, Optional, Set

from dotenv import load_dotenv

# Główne ścieżki
BASE_DIR = Path(__file__).resolve().parent.parent

# Ładuj .env z katalogu głównego (jeśli istnieje).
load_dotenv(BASE_DIR / ".env")

# Katalog z surowymi danymi MES
RAW_DATA_DIR = BASE_DIR / "data" / "raw"

# Nazwy plików szukanych przez auto-detect (kolejność = priorytet).
# Pierwszy znaleziony wygrywa. HansAA ma Dział ZP — stary eksport nie ma.
RAW_DATA_FILENAMES = [
    "HansAA_AI_KiT_v8_9_PRODvsKiT.csv",
    "Dane Mes DKR ZP ZAKOŃCZONE.csv",
    "Dane Mes DKR ZP ZAKOŃCZONE.xlsx",
]


def find_raw_data_file() -> Optional[Path]:
    """
    Znajduje plik źródłowy MES (auto-detect wg kolejności RAW_DATA_FILENAMES).
    Sprawdza kolejno: data/raw/, BASE_DIR. Zwraca ścieżkę lub None.
    """
    search_dirs = [RAW_DATA_DIR, BASE_DIR]
    for filename in RAW_DATA_FILENAMES:
        for d in search_dirs:
            candidate = d / filename
            if candidate.exists():
                return candidate
    return None


# Zachowane dla wstecznej kompatybilności — faktyczne użycie w find_raw_data_file()
RAW_DATA_PATH = find_raw_data_file() or (RAW_DATA_DIR / RAW_DATA_FILENAMES[0])

# Baza danych SQLite
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
DB_PATH = PROCESSED_DATA_DIR / "baza_mes.sqlite"

# Katalogi pomocnicze
SAMPLES_DIR = BASE_DIR / "data" / "samples"
DXF_DIR = BASE_DIR / "dxf"

# Warstwy DXF
DEFAULT_CUT_LAYERS: Set[str] = {
    "CUT",
    "INTERNAL_CUT",
    "CIECIE",
    "OUTLINE",
    "OBRYS",
    "NOTCH",
    "0",
    "KONTUR",
}

DEFAULT_DRAW_LAYERS: Set[str] = {
    "PEN",
    "DRAW",
    "RYSOWANIE",
    "TEXT",
    "PISAK",
    "OPIS",
    "ZAGINANIE",
    "8",
}

# ==============================================================================
# SILNIK DOPASOWANIA (Similarity Engine)
# ==============================================================================
# Wagi trybu hybrydowego DXF + kod + BOM (3-składnikowy, nowy standard).
#   S = (w_klient·S_klient + w_geom·S_geom + w_bom·S_bom) / (w_klient+w_geom+w_bom)
# Gdy BOM brak u zapytania — wagi renormalizowane do (w_klient : w_geom).
# Gdy BOM brak u kandydata (a zapytanie ma BOM) — kandydat dostaje neutralne
# S_bom = BOM_NEUTRAL_SIMILARITY, wagi pozostają pełne (wariant B, spójny UX).
WEIGHT_CLIENT: float = 0.15
WEIGHT_GEOM: float = 0.45
WEIGHT_BOM: float = 0.40

# Parametry składowej S_bom.
#   S_precyzja = BOM_PRECYZJA_JACCARD · Jaccard(kody) + BOM_PRECYZJA_ILOSC · średnia_sim_ilości
#   S_struktura = 1 − L1(udziały kategorii) / 2
#   S_bom       = BOM_ALPHA_PRECYZJA · S_precyzja + (1 − BOM_ALPHA_PRECYZJA) · S_struktura
BOM_ALPHA_PRECYZJA: float = 0.70
BOM_PRECYZJA_JACCARD: float = 0.75
BOM_PRECYZJA_ILOSC: float = 0.25
BOM_MAX_DEPTH: int = 3

# Neutralna ocena S_bom dla kandydata bez BOM, gdy zapytanie ma BOM.
# Środek skali (0..1): kandydat nie jest karany zerem za brak danych,
# ale też nie jest nagradzany powyżej kandydatów z realnym, niepasującym BOM-em.
# Używane w obu ścieżkach: `find_similar` (DXF + kod + BOM) i
# `_rank_with_bom_only` (kod + BOM bez DXF). Spójne UX.
BOM_NEUTRAL_SIMILARITY: float = 0.5

# Wagi silnika dopasowania — tryb TYLKO KOD (bez DXF, bez BOM)
# S = W_KL · S_klient + W_DATA · S_data + W_REL · reliability
# - S_klient: 1.0 gdy klient zgodny, w praktyce zawsze 1.0 (filtrujemy po kliencie)
# - S_data:   1 / (1 + Δmiesięcy / 12) — im bliższe daty (MMYY), tym wyższe
# - reliability: log(1 + samples) / log(1 + max_samples) — premia za wiarygodność statystyczną
WEIGHT_CODE_CLIENT: float = 0.55
WEIGHT_CODE_DATE: float = 0.35
WEIGHT_CODE_RELIABILITY: float = 0.10

# Domyślne wartości normalizacyjne dla wektorów geometrii
DEFAULT_NORM_AREA_M2: float = 25.0
DEFAULT_NORM_CUT_LEN_M: float = 50.0
DEFAULT_NORM_ASPECT_RATIO: float = 10.0

# Procesy kwalifikowane jako operacje cięcia/krojenia
CUTTING_PROCESS_CODES: Set[str] = {
    "KROJENIE",
    "RĘCZNE KROJENIE",
    "RECZNE KROJENIE",
    "KROJENIE ELEMENTÓW",
    "KROJENIE ELEMENTOW",
    "KROJENIE 2",
    "CIECIE",
    "CIĘCIE",
}

# Filtry danych MES
MIN_TIME_PER_UNIT_MIN: float = 0.001
MAX_TIME_PER_UNIT_MIN: float = 1440.0  # max 24h na 1 sztukę


# ==============================================================================
# SKALA RYSUNKU DXF
# ==============================================================================
DRAWING_SCALE: float = 10.0


# ==============================================================================
# KALKULATOR KROJU — MNOŻNIKI MASZYN
# ==============================================================================
MACHINE_CUTTING_MULTIPLIERS: Dict[str, float] = {
    "ZUND": 0.08307067,
    "LECTRA": 0.090474006,
    "JIGWEI": 0.101171631,
}
FRAME_MULTIPLIER: float = 1.08748


# ==============================================================================
# ERP XL — KONFIGURACJA POŁĄCZENIA (z .env)
# ==============================================================================
ERP_SERVER: str = os.getenv("ERP_SERVER", "win2019kd")
ERP_DATABASE: str = os.getenv("ERP_DATABASE", "ERPXL_HansAA")
ERP_DRIVER: str = os.getenv("ERP_DRIVER", "SQL Server Native Client 11.0")
ERP_VIEW: str = os.getenv("ERP_VIEW", "_ha_bk_dkr_mes_v2")
ERP_BOM_VIEW: str = os.getenv("ERP_BOM_VIEW", "_im_mm_kalkulacja_Excel")
ERP_UID: str = os.getenv("ERP_UID", "")
ERP_PWD: str = os.getenv("ERP_PWD", "")
ERP_CONNECTION_TIMEOUT: int = int(os.getenv("ERP_CONNECTION_TIMEOUT", "15"))

# Okno przyrostowego odświeżania — ile dni wstecz pytamy ERP o rekordy.
# Rekordy starsze są pomijane, chyba że PZL_Status != 'zamknięte'.
INCREMENTAL_LOOKBACK_DAYS: int = 90


def has_erp_credentials() -> bool:
    """True, jeśli w .env uzupełniono UID i hasło ERP."""
    return bool(ERP_UID and ERP_PWD)


# ==============================================================================
# BOM — OCHRONA DANYCH FINANSOWYCH
# ==============================================================================
# Hasło do odblokowania widoczności stawek i wartości PLN w BOM.
# Puste = brak konfiguracji → dane finansowe są trwale ukryte w UI
# (bezpieczeństwo domyślne: brak hasła = brak dostępu, nie „brak hasła = wszystko widoczne").
BOM_FINANCE_PASSWORD: str = os.getenv("BOM_FINANCE_PASSWORD", "")


def has_bom_finance_password() -> bool:
    """True, jeśli w .env skonfigurowano hasło do finansów BOM."""
    return bool(BOM_FINANCE_PASSWORD)


def is_bom_finance_password_valid(password: Optional[str]) -> bool:
    """
    Sprawdza hasło do finansów BOM w stałym czasie (constant-time),
    żeby utrudnić atak timingowy na porównanie.

    Zwraca False, gdy hasło nie jest skonfigurowane w .env — brak hasła
    oznacza, że funkcja odblokowania jest niedostępna (domyślnie bezpiecznie).

    :param password: hasło wpisane przez użytkownika (może być None / pusty).
    :return: True tylko gdy hasło skonfigurowane i identyczne.
    """
    if not BOM_FINANCE_PASSWORD or not password:
        return False
    return secrets.compare_digest(password, BOM_FINANCE_PASSWORD)


# ==============================================================================
# HELPERY SKALI
# ==============================================================================
def to_real_mm(value_mm_dxf: float) -> float:
    """Konwertuje surowe mm z DXF na rzeczywiste mm (skala 1:10)."""
    return value_mm_dxf * DRAWING_SCALE


def to_real_m(value_m_dxf: float) -> float:
    """Konwertuje surowe metry z DXF na rzeczywiste metry (skala 1:10)."""
    return value_m_dxf * DRAWING_SCALE


def to_real_m2(value_m2_dxf: float) -> float:
    """Konwertuje surowe m² z DXF na rzeczywiste m² (skala 1:10 → pole ×100)."""
    return value_m2_dxf * (DRAWING_SCALE * DRAWING_SCALE)