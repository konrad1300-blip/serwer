"""Moduł wyszukiwania wyrobów analogicznych / podobnych (Procesor 3).

Tryby dopasowania:

1. Hybrydowy pełny (DXF + kod + BOM) — `find_similar()`:
   S = (w_klient·S_klient + w_geom·S_geom + w_bom·S_bom) / ΣW
   - brak BOM u zapytania   → renormalizacja wag do (w_klient : w_geom),
   - brak BOM u kandydata   → S_bom = BOM_NEUTRAL_SIMILARITY (0.5), wagi pełne.

2. Kod + BOM (bez DXF) — `find_similar_by_code()` gdy zapytanie ma BOM
   i przynajmniej jeden kandydat ma BOM:
   S = (w_klient·S_klient + w_bom·S_bom) / (w_klient + w_bom)
   Kandydaci bez BOM wchodzą z S_bom = BOM_NEUTRAL_SIMILARITY.

3. Tylko kod (bez DXF i bez BOM) — `find_similar_by_code()` fallback:
   S = W_KL·S_klient + W_DATA·S_data + W_REL·reliability
   Priorytet: klient (XXX), potem bliskość daty (MMYY), potem wiarygodność statystyczna.

Struktura kodu produktu: XXX-YYYY-ZZZ, gdzie YYYY = MMYY
(dwie pierwsze cyfry = miesiąc, dwie ostatnie = rok, np. 0926 = wrzesień 2026).
"""
import argparse
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.config import (
    BOM_ALPHA_PRECYZJA,
    BOM_NEUTRAL_SIMILARITY,
    BOM_PRECYZJA_ILOSC,
    BOM_PRECYZJA_JACCARD,
    DB_PATH,
    WEIGHT_BOM,
    WEIGHT_CLIENT,
    WEIGHT_CODE_CLIENT,
    WEIGHT_CODE_DATE,
    WEIGHT_CODE_RELIABILITY,
    WEIGHT_GEOM,
)
from src.models import BOMItem, DXFFeatures, MatchResult
from src.processors.bom_processor import get_flattened_bom
from src.processors.dxf_processor import DXFProcessor


# Wzorzec kodu produktu XXX-YYYY-ZZZ (XXX=klient, YYYY=MMYY, ZZZ=numer).
_PRODUCT_CODE_RE = re.compile(r"^(\d{3})-(\d{2})(\d{2})-(\d+)$")


def _parse_product_code(code: str) -> Optional[Tuple[str, int, int]]:
    """
    Rozbiera kod produktu XXX-YYYY-ZZZ na (klient, rok, miesiąc).

    YYYY interpretujemy jako MMYY (pierwsze dwie = miesiąc, ostatnie dwie = rok 2000+).
    Zwraca None gdy format nie pasuje lub miesiąc poza zakresem 1..12.
    """
    if not code:
        return None
    m = _PRODUCT_CODE_RE.match(code.strip())
    if not m:
        return None
    client = m.group(1)
    month = int(m.group(2))
    year_2 = int(m.group(3))
    if not (1 <= month <= 12):
        return None
    year = 2000 + year_2
    return client, year, month


def _month_distance(y1: int, m1: int, y2: int, m2: int) -> int:
    """Zwraca bezwzględną odległość w miesiącach między dwiema datami (YYYY, MM)."""
    return abs((y1 * 12 + m1) - (y2 * 12 + m2))


# ==============================================================================
# SKŁADOWA S_bom — KOMPOZYCJA PRECYZJI I STRUKTURY
# ==============================================================================
def _category_of(ptz_kod: str) -> str:
    """Zwraca kategorię materiału (prefiks 3 znaków kodu PTZ lub 'OTHER')."""
    kod = (ptz_kod or "").strip()
    if len(kod) >= 3 and kod.startswith("M"):
        return kod[:3]
    return "OTHER"


def _quantity_similarity(qv: float, cv: float) -> float:
    """
    Podobieństwo ilości dla jednego wspólnego kodu.

    Wzór: 1 / (1 + |q−c| / max(q, c)).
    Identyczne ilości → 1.0; dwukrotna różnica → 0.67; dziesięciokrotna → 0.53.
    """
    mx = max(qv, cv)
    if mx <= 0:
        return 1.0 if qv == cv else 0.0
    return 1.0 / (1.0 + abs(qv - cv) / mx)


def _category_shares(items: List[BOMItem]) -> Dict[str, float]:
    """Udziały kategorii w sumie ilości (sumują się do 1.0, lub {} gdy brak ilości)."""
    sums: Dict[str, float] = {}
    total = 0.0
    for it in items:
        cat = _category_of(it.ptz_kod)
        q = it.quantity or 0.0
        sums[cat] = sums.get(cat, 0.0) + q
        total += q
    if total <= 0:
        return {}
    return {k: v / total for k, v in sums.items()}


def _compute_bom_similarity(
    query_items: List[BOMItem],
    candidate_items: List[BOMItem],
) -> Optional[dict]:
    """
    Liczy S_bom (0..1) z dwóch BOM-ów: zapytania i kandydata.

    Zwraca dict z rozbiciem (`s_bom`, `precyzja`, `struktura`, `jaccard`, `ilosc`)
    albo None gdy któryś BOM jest pusty (brak danych = brak oceny).

    Kształt (zgodnie z decyzjami projektowymi):
    - Precyzja (obecność + zgodność ilości kodów):
      S_precyzja = BOM_PRECYZJA_JACCARD · Jaccard(kody) + BOM_PRECYZJA_ILOSC · średnia_sim_ilości
    - Struktura (podobieństwo udziałów kategorii M01..M15):
      S_struktura = max(0, 1 − L1(q_shares, c_shares) / 2)
    - Kompozycja:
      S_bom = BOM_ALPHA_PRECYZJA · S_precyzja + (1 − BOM_ALPHA_PRECYZJA) · S_struktura

    Uwaga o duplikatach: ten sam `ptz_kod` może wystąpić na wejściu wielokrotnie
    (np. wyrób ma ten sam materiał bezpośrednio i przez półprodukt). Ilości
    są sumowane, zgodnie z regułą biznesową ERP (agregacja po PTZ_Kod).
    """
    if not query_items or not candidate_items:
        return None

    q_codes = {it.ptz_kod for it in query_items}
    c_codes = {it.ptz_kod for it in candidate_items}
    union = q_codes | c_codes
    if not union:
        return None

    jaccard = len(q_codes & c_codes) / len(union)

    # Agregacja ilości po kodzie — duplikaty sumują się (nie nadpisują).
    q_qty: Dict[str, float] = defaultdict(float)
    for it in query_items:
        q_qty[it.ptz_kod] += it.quantity

    c_qty: Dict[str, float] = defaultdict(float)
    for it in candidate_items:
        c_qty[it.ptz_kod] += it.quantity

    common = q_codes & c_codes
    if common:
        s_ilosc = sum(_quantity_similarity(q_qty[k], c_qty[k]) for k in common) / len(common)
    else:
        s_ilosc = 0.0

    precyzja = BOM_PRECYZJA_JACCARD * jaccard + BOM_PRECYZJA_ILOSC * s_ilosc

    q_shares = _category_shares(query_items)
    c_shares = _category_shares(candidate_items)
    all_cats = set(q_shares) | set(c_shares)
    if all_cats:
        l1 = sum(abs(q_shares.get(k, 0.0) - c_shares.get(k, 0.0)) for k in all_cats)
        struktura = max(0.0, 1.0 - l1 / 2.0)
    else:
        struktura = 0.0

    s_bom = BOM_ALPHA_PRECYZJA * precyzja + (1.0 - BOM_ALPHA_PRECYZJA) * struktura

    return {
        "s_bom": round(s_bom, 4),
        "precyzja": round(precyzja, 4),
        "struktura": round(struktura, 4),
        "jaccard": round(jaccard, 4),
        "ilosc": round(s_ilosc, 4),
    }


# ==============================================================================
# SILNIK DOPASOWANIA
# ==============================================================================
class SimilarityEngine:
    """
    Silnik dopasowania hybrydowego (3-składnikowy):
    S = (w_klient·S_klient + w_geom·S_geom + w_bom·S_bom) / (Σ wag)

    Semantyka braku BOM (wariant B):
    - brak BOM u ZAPYTANIA   → wagi renormalizowane do (w_klient : w_geom),
    - brak BOM u KANDYDATA   → kandydat dostaje neutralne
                                S_bom = BOM_NEUTRAL_SIMILARITY (0.5), wagi pełne.

    Brak kandydatów tego samego klienta → w_klient = 0, reszta proporcjonalnie.

    Tryby dopasowania (find_similar_by_code):
    - kod + BOM (gdy zapytanie ma BOM i przynajmniej jeden kandydat ma BOM),
    - kod + data + reliability (fallback gdy zapytanie nie ma BOM lub nikt
      z kandydatów go nie ma).
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        weight_client: float = WEIGHT_CLIENT,
        weight_geom: float = WEIGHT_GEOM,
        weight_bom: float = WEIGHT_BOM,
    ):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.weight_client = weight_client
        self.weight_geom = weight_geom
        self.weight_bom = weight_bom

    # ------------------------------------------------------------------
    # Wspólne zapytania do bazy
    # ------------------------------------------------------------------
    def _get_candidates_with_features(self) -> List[dict]:
        """
        Pobiera z bazy produkty posiadające profile MES i cechy DXF.

        Zwraca pustą listę, jeśli baza nie istnieje lub tabela
        `product_dxf_features` nie została jeszcze zaindeksowana.
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT 
                        p.product_code,
                        p.client_code,
                        p.product_name,
                        d.filename,
                        d.filenames_json,
                        d.files_count,
                        d.bounding_box_width_mm,
                        d.bounding_box_height_mm,
                        d.bounding_box_area_m2,
                        d.total_cut_length_m,
                        d.drawing_length_m,
                        d.contours_count,
                        d.aspect_ratio
                    FROM product_profiles p
                    INNER JOIN product_dxf_features d ON p.product_code = d.product_code;
                """)
            except sqlite3.OperationalError:
                return []

            rows = cursor.fetchall()
            candidates = []
            for r in rows:
                try:
                    filenames_all = json.loads(r[4]) if r[4] else [r[3]]
                except (json.JSONDecodeError, TypeError):
                    filenames_all = [r[3]] if r[3] else []

                candidates.append({
                    "product_code": r[0],
                    "client_code": r[1],
                    "product_name": r[2] or "",
                    "dxf_filename": r[3] or "",
                    "filenames_all": filenames_all,
                    "files_count": int(r[5]) if r[5] is not None else 1,
                    "width_mm": float(r[6]),
                    "height_mm": float(r[7]),
                    "area_m2": float(r[8]),
                    "cut_length_m": float(r[9]),
                    "drawing_length_m": float(r[10]),
                    "contours_count": int(r[11]),
                    "aspect_ratio": float(r[12]),
                })
            return candidates
        finally:
            conn.close()

    def _get_profiles_by_client(self, client_code: str) -> List[dict]:
        """
        Pobiera produkty danego klienta z bazy (kod, nazwa, liczba prób).
        Używane w trybie tylko-kod — filtrujemy po kliencie już na poziomie SQL.
        """
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT product_code, client_code, product_name, total_samples
                    FROM product_profiles
                    WHERE client_code = ?
                    ORDER BY product_code;
                """, (client_code,))
            except sqlite3.OperationalError:
                return []
            rows = cursor.fetchall()
            return [
                {
                    "product_code": r[0],
                    "client_code": r[1],
                    "product_name": r[2] or "",
                    "sample_count": int(r[3] or 0),
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Tryb 1: DXF + kod + BOM (hybrydowy, 3-składnikowy)
    # ------------------------------------------------------------------
    def find_similar(
        self,
        query_code: str,
        dxf_features: DXFFeatures,
        top_k: int = 5,
        w_client: Optional[float] = None,
        w_geom: Optional[float] = None,
        w_bom: Optional[float] = None,
    ) -> List[MatchResult]:
        """
        Wyznacza ranking najbardziej podobnych wyrobów historycznych.

        Uwzględnia trzy składowe: zgodność klienta, podobieństwo geometrii DXF
        oraz podobieństwo struktury BOM.

        Semantyka braku BOM:
        - brak BOM u zapytania  → renormalizacja wag do (w_klient : w_geom),
        - brak BOM u kandydata  → neutralne S_bom = BOM_NEUTRAL_SIMILARITY (0.5),
                                  wagi pozostają pełne (bez renormalizacji).
        """
        w_client = self.weight_client if w_client is None else w_client
        w_geom = self.weight_geom if w_geom is None else w_geom
        w_bom = self.weight_bom if w_bom is None else w_bom

        candidates = self._get_candidates_with_features()
        if not candidates:
            return []

        query_code_clean = query_code.strip()
        query_client = query_code_clean[:3]

        query_bom_items = get_flattened_bom(query_code_clean, db_path=self.db_path)
        query_has_bom = bool(query_bom_items)

        bom_cache: Dict[str, List[BOMItem]] = {}

        def _bom_of(code: str) -> List[BOMItem]:
            if code not in bom_cache:
                bom_cache[code] = get_flattened_bom(code, db_path=self.db_path)
            return bom_cache[code]

        client_candidates_count = sum(1 for c in candidates if c["client_code"] == query_client)
        if client_candidates_count == 0:
            eff_w_client = 0.0
            eff_w_geom = w_geom
            eff_w_bom = w_bom
        else:
            eff_w_client = w_client
            eff_w_geom = w_geom
            eff_w_bom = w_bom

        max_area = max(max(c["area_m2"] for c in candidates), dxf_features.bounding_box_area_m2, 1.0)
        max_cut = max(max(c["cut_length_m"] for c in candidates), dxf_features.total_cut_length_m, 1.0)
        sample_ratios = [min(c["aspect_ratio"], 20.0) for c in candidates]
        max_ratio = max(max(sample_ratios), min(dxf_features.aspect_ratio, 20.0), 1.0)

        results: List[MatchResult] = []
        for c in candidates:
            is_client_match = (c["client_code"] == query_client)
            s_client = 1.0 if is_client_match else 0.0

            delta_a = abs(dxf_features.bounding_box_area_m2 - c["area_m2"])
            delta_l = abs(dxf_features.total_cut_length_m - c["cut_length_m"])
            delta_r = abs(dxf_features.aspect_ratio - c["aspect_ratio"])

            d = math.sqrt(
                (delta_a / max_area) ** 2 +
                (delta_l / max_cut) ** 2 +
                (delta_r / max_ratio) ** 2
            )
            s_geom = 1.0 / (1.0 + d)

            s_bom: Optional[float] = None
            bom_breakdown: Optional[dict] = None
            bom_used = False

            if query_has_bom:
                cand_items = _bom_of(c["product_code"])
                if cand_items:
                    bom_result = _compute_bom_similarity(query_bom_items, cand_items)
                    if bom_result is not None:
                        s_bom = bom_result["s_bom"]
                        bom_breakdown = bom_result
                        bom_used = True

            if query_has_bom:
                # Wariant B: brak BOM u kandydata → neutralne S_bom (bez renormalizacji).
                s_bom_effective = s_bom if s_bom is not None else BOM_NEUTRAL_SIMILARITY
                total_w = eff_w_client + eff_w_geom + eff_w_bom
                total_similarity = (
                    (eff_w_client * s_client + eff_w_geom * s_geom + eff_w_bom * s_bom_effective) / total_w
                    if total_w > 0 else 0.0
                )
            else:
                # Brak BOM u zapytania → renormalizacja do (w_klient : w_geom).
                total_w = eff_w_client + eff_w_geom
                total_similarity = (
                    (eff_w_client * s_client + eff_w_geom * s_geom) / total_w
                    if total_w > 0 else 0.0
                )

            dxf_filename = c["dxf_filename"] or f"AI{c['product_code']}.dxf"

            cand_dxf = DXFFeatures(
                filename=dxf_filename,
                filenames_all=c["filenames_all"],
                files_count=c["files_count"],
                bounding_box_width_mm=c["width_mm"],
                bounding_box_height_mm=c["height_mm"],
                bounding_box_area_m2=c["area_m2"],
                total_cut_length_m=c["cut_length_m"],
                drawing_length_m=c["drawing_length_m"],
                contours_count=c["contours_count"],
                layers_found=[],
                aspect_ratio=c["aspect_ratio"],
            )

            results.append(MatchResult(
                matched_product_code=c["product_code"],
                matched_product_name=c["product_name"],
                client_code=c["client_code"],
                similarity_score=round(total_similarity, 4),
                client_match=is_client_match,
                dxf_distance=round(d, 4),
                dxf_features=cand_dxf,
                bom_similarity=s_bom,
                bom_used=bom_used,
                bom_breakdown=bom_breakdown,
            ))

        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Tryb 2: Tylko kod (bez DXF)
    # ------------------------------------------------------------------
    def find_similar_by_code(
        self,
        query_code: str,
        top_k: int = 5,
    ) -> List[MatchResult]:
        """
        Wyszukuje wyroby podobne na podstawie samego kodu produktu (bez DXF).

        Hierarchia ścieżek wewnątrz tej metody:

        1. Kod + BOM (preferowana): jeżeli zapytanie ma BOM i przynajmniej
           jeden kandydat też ma BOM → ranking liczony wzorem:
             S = (w_klient · S_klient + w_bom · S_bom) / (w_klient + w_bom)
           Kandydaci bez BOM wchodzą z neutralnym S_bom = BOM_NEUTRAL_SIMILARITY.

        2. Kod + data + reliability (fallback): gdy zapytanie nie ma BOM lub
           żaden kandydat nie ma BOM → stary wzór:
             S = W_KL·S_klient + W_DATA·S_date + W_REL·reliability

        :param query_code: kod zapytania w formacie XXX-YYYY-ZZZ.
        :param top_k: liczba wyrobów w rankingu.
        :return: lista MatchResult (z dxf_features=None, dxf_distance=0.0).
        """
        query = _parse_product_code(query_code)
        if query is None:
            return []
        q_client, q_year, q_month = query

        candidates = self._get_profiles_by_client(q_client)
        if not candidates:
            return []

        # Sprawdź, czy zapytanie ma BOM oraz czy jest jakikolwiek kandydat z BOM.
        query_bom_items = get_flattened_bom(query_code.strip(), db_path=self.db_path)
        query_has_bom = bool(query_bom_items)

        bom_cache: Dict[str, List[BOMItem]] = {}

        def _bom_of(code: str) -> List[BOMItem]:
            if code not in bom_cache:
                bom_cache[code] = get_flattened_bom(code, db_path=self.db_path)
            return bom_cache[code]

        any_candidate_has_bom = False
        if query_has_bom:
            for c in candidates:
                if _bom_of(c["product_code"]):
                    any_candidate_has_bom = True
                    break

        if query_has_bom and any_candidate_has_bom:
            return self._rank_with_bom_only(
                candidates, query_bom_items, _bom_of, top_k,
            )
        return self._rank_with_date_reliability(
            candidates, q_year, q_month, top_k,
        )

    # ------------------------------------------------------------------
    # Ścieżka A: kod + BOM (bez DXF)
    # ------------------------------------------------------------------
    def _rank_with_bom_only(
        self,
        candidates: List[dict],
        query_bom_items: List[BOMItem],
        bom_getter,
        top_k: int,
    ) -> List[MatchResult]:
        """
        Ranking 2-składnikowy: klient (twardo = 1.0, bo już przefiltrowany)
        + BOM. Wagi renormalizowane do (w_klient : w_bom).

        Semantyka braku BOM (wariant B): kandydaci bez BOM nie są wykluczani
        — dostają neutralne S_bom = BOM_NEUTRAL_SIMILARITY (0.5). Spójne
        z `find_similar` (DXF + kod + BOM).
        """
        total_w = self.weight_client + self.weight_bom
        if total_w <= 0:
            return []

        results: List[MatchResult] = []
        for c in candidates:
            cand_bom = bom_getter(c["product_code"])
            if not cand_bom:
                # Brak BOM u kandydata → neutralne S_bom, wpis w rankingu.
                s_bom = BOM_NEUTRAL_SIMILARITY
                bom_result = None
                bom_used = False
            else:
                bom_result = _compute_bom_similarity(query_bom_items, cand_bom)
                if bom_result is None:
                    continue
                s_bom = bom_result["s_bom"]
                bom_used = True

            s_client = 1.0  # klient zawsze zgodny (już przefiltrowany po kliencie)
            s_total = (
                self.weight_client * s_client + self.weight_bom * s_bom
            ) / total_w

            results.append(MatchResult(
                matched_product_code=c["product_code"],
                matched_product_name=c["product_name"],
                client_code=c["client_code"],
                similarity_score=round(s_total, 4),
                client_match=True,
                dxf_distance=0.0,
                dxf_features=None,
                bom_similarity=s_bom if bom_used else None,
                bom_used=bom_used,
                bom_breakdown=bom_result,
            ))

        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Ścieżka B: kod + data + reliability (fallback)
    # ------------------------------------------------------------------
    def _rank_with_date_reliability(
        self,
        candidates: List[dict],
        q_year: int,
        q_month: int,
        top_k: int,
    ) -> List[MatchResult]:
        """
        Fallback bez BOM-u. Priorytet:
        1. Zgodność klienta (XXX) — twardy filtr po SQL.
        2. Bliskość daty (YYYY = MMYY) — im mniejsza różnica miesięcy, tym wyżej.
        3. Wiarygodność statystyczna — log(1+samples) premiuje wyroby z historią.
        """
        max_samples = max((c["sample_count"] for c in candidates), default=0)
        log_max = math.log(1 + max_samples) if max_samples > 0 else 1.0

        results: List[MatchResult] = []
        for c in candidates:
            parsed = _parse_product_code(c["product_code"])
            if parsed is None:
                continue
            _, c_year, c_month = parsed

            s_client = 1.0
            dist = _month_distance(q_year, q_month, c_year, c_month)
            s_date = 1.0 / (1.0 + dist / 12.0)

            samples = c["sample_count"] or 0
            reliability = (
                math.log(1 + samples) / log_max
                if samples > 0 and log_max > 0
                else 0.0
            )

            s_code = (
                WEIGHT_CODE_CLIENT * s_client
                + WEIGHT_CODE_DATE * s_date
                + WEIGHT_CODE_RELIABILITY * reliability
            )

            results.append(MatchResult(
                matched_product_code=c["product_code"],
                matched_product_name=c["product_name"],
                client_code=c["client_code"],
                similarity_score=round(s_code, 4),
                client_match=True,
                dxf_distance=0.0,
                dxf_features=None,
            ))

        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:top_k]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Silnik dopasowania wyrobów podobnych.")
    parser.add_argument("--kod", type=str, required=True, help="Nowy kod produktu.")
    parser.add_argument("--dxf", type=str, default=None,
                        help="Ścieżka do pliku DXF (opcjonalna). Bez DXF użyty tryb tylko-kod.")
    parser.add_argument("--top", type=int, default=5, help="Liczba wyrobów w rankingu.")
    args = parser.parse_args()

    engine = SimilarityEngine()

    if args.dxf:
        dxf_proc = DXFProcessor()
        features = dxf_proc.extract_features(args.dxf)
        top_matches = engine.find_similar(query_code=args.kod, dxf_features=features, top_k=args.top)
        tryb = "DXF + kod + BOM"
    else:
        top_matches = engine.find_similar_by_code(query_code=args.kod, top_k=args.top)
        tryb = "tylko kod (auto: BOM lub data+reliability)"

    print("=" * 80)
    print(f"🔍 WYNIKI DOPASOWANIA ({tryb}) DLA KODU: {args.kod}")
    print("=" * 80)
    if not top_matches:
        print("❌ Brak dopasowań (klient nieobecny w bazie lub baza pusta).")
    else:
        for i, m in enumerate(top_matches, 1):
            client_label = "Zgodny" if m.client_match else "Inny"
            bom_lbl = ""
            if m.bom_used and m.bom_similarity is not None:
                bom_lbl = f" | BOM: {m.bom_similarity:.2f}"
            print(f"{i:<4} | {m.matched_product_code:<15} | {m.similarity_percent:>5.1f}%       | {client_label:<12}{bom_lbl} | {m.matched_product_name[:30]}")
    print("=" * 80)