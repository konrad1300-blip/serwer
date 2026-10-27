"""Klasy danych i kontrakty (Data Models) dla systemu estymacji czasów."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DXFFeatures:
    """Reprezentuje wyekstrahowane cechy geometryczne z pliku DXF (wartości surowe)."""
    filename: str
    bounding_box_width_mm: float
    bounding_box_height_mm: float
    bounding_box_area_m2: float
    total_cut_length_m: float
    drawing_length_m: float
    contours_count: int
    layers_found: List[str] = field(default_factory=list)
    aspect_ratio: float = 0.0
    filenames_all: List[str] = field(default_factory=list)
    files_count: int = 1

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "filenames_all": self.filenames_all,
            "files_count": self.files_count,
            "bounding_box_width_mm": self.bounding_box_width_mm,
            "bounding_box_height_mm": self.bounding_box_height_mm,
            "bounding_box_area_m2": self.bounding_box_area_m2,
            "total_cut_length_m": self.total_cut_length_m,
            "drawing_length_m": self.drawing_length_m,
            "contours_count": self.contours_count,
            "layers_found": self.layers_found,
            "aspect_ratio": self.aspect_ratio,
        }


@dataclass
class ProcessTimeStat:
    """Statystyki czasowe dla pojedynczego procesu technologicznego z bazy MES."""
    process_code: str
    process_name: str
    median_time_per_unit_min: float
    min_time_per_unit_min: float
    max_time_per_unit_min: float
    sample_count: int
    q25_time_per_unit_min: float = 0.0
    q50_time_per_unit_min: float = 0.0
    q75_time_per_unit_min: float = 0.0


@dataclass
class ProductProfile:
    """Profil wyrobu zgromadzonego w bazie wiedzy MES."""
    product_code: str
    client_code: str
    product_name: str
    processes: Dict[str, ProcessTimeStat] = field(default_factory=dict)
    dxf_features: Optional[DXFFeatures] = None

    @property
    def total_median_time_min(self) -> float:
        return sum(p.median_time_per_unit_min for p in self.processes.values())


@dataclass
class MatchResult:
    """
    Wynik dopasowania produktu z bazy do zapytania użytkownika.

    Pola BOM (`bom_similarity`, `bom_used`, `bom_breakdown`) są wypełniane
    wyłącznie w trybie hybrydowym DXF + kod + BOM. W trybie tylko-kod
    pozostają domyślne (`None` / `False`).
    """
    matched_product_code: str
    matched_product_name: str
    client_code: str
    similarity_score: float
    client_match: bool
    dxf_distance: float
    dxf_features: Optional[DXFFeatures] = None

    # Składowa BOM — diagnostyka i wsparcie UI.
    bom_similarity: Optional[float] = None
    bom_used: bool = False
    bom_breakdown: Optional[dict] = None

    @property
    def similarity_percent(self) -> float:
        return round(self.similarity_score * 100.0, 1)


@dataclass
class MachineCuttingTime:
    """Przewidywany czas kroju dla konkretnej maszyny."""
    machine_name: str
    cutting_time_min: float

    @property
    def cutting_time_hours(self) -> float:
        return self.cutting_time_min / 60.0


@dataclass
class RawOperation:
    """Surowe odbicie pojedynczej operacji MES (do analizy ZP-ków)."""
    product_code: str
    process_code: str
    process_name: str
    product_name: str
    client_code: str
    zp_number: str
    zs_number: str
    real_time_per_unit_min: float
    unit_count: int
    planned_time_total_min: Optional[float] = None
    planned_time_per_unit_min: Optional[float] = None
    norm_time_total_min: Optional[float] = None
    norm_time_per_unit_min: Optional[float] = None
    dzial_zp: Optional[str] = None


@dataclass
class EstimatedProcess:
    """Pojedynczy proces technologiczny z oszacowanym czasem."""
    process_code: str
    process_name: str
    estimated_time_min: float
    min_time_min: float
    max_time_min: float
    is_scaled: bool = False
    scaling_factor: float = 1.0
    sample_count: int = 0
    q25_time_min: float = 0.0
    q50_time_min: float = 0.0
    q75_time_min: float = 0.0


@dataclass
class EstimationResult:
    """Kompletny wynik estymacji technologicznej."""
    target_product_code: str
    reference_product_code: str
    reference_product_name: str
    scaling_factor: float
    processes: List[EstimatedProcess] = field(default_factory=list)
    total_estimated_time_min: float = 0.0
    total_min_time_min: float = 0.0
    total_max_time_min: float = 0.0
    total_q25_min: float = 0.0
    total_q50_min: float = 0.0
    total_q75_min: float = 0.0
    machine_cutting_times: List[MachineCuttingTime] = field(default_factory=list)
    raw_cut_length_dxf_mm: float = 0.0

    @property
    def total_estimated_hours(self) -> float:
        return self.total_estimated_time_min / 60.0

    @property
    def total_min_hours(self) -> float:
        return self.total_min_time_min / 60.0

    @property
    def total_max_hours(self) -> float:
        return self.total_max_time_min / 60.0


# ==============================================================================
# BOM — BILL OF MATERIALS (z ERP XL)
# ==============================================================================
@dataclass
class BOMItem:
    """Pojedyncza pozycja w BOM (materiał lub półprodukt)."""
    ptz_kod: str
    ptz_nazwa: str
    quantity: float
    unit: str
    stawka: float
    wartosc_pln: float
    typ: str
    twr_typ: int
    is_semiproduct: bool = False


@dataclass
class BOMTechnology:
    """Technologia produktu w konkretnej wersji i rewizji."""
    product_code: str          # rdzeń XXX-XXXX-XXX
    full_pte_kod: str          # pełny kod z sufiksem _RxxVxx (jeśli był)
    pte_nazwa: str
    revision: int              # 0 gdy brak sufiksu
    version: int               # 0 gdy brak sufiksu
    items: List[BOMItem] = field(default_factory=list)

    @property
    def items_count(self) -> int:
        return len(self.items)

    @property
    def total_value_pln(self) -> float:
        return sum(i.wartosc_pln for i in self.items)

    @property
    def has_revision_suffix(self) -> bool:
        return self.revision > 0 or self.version > 0