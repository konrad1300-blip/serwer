"""Moduł analizy i ekstrakcji cech z plików DXF (Procesor 2)."""
import argparse
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import ezdxf

from src.config import (
    DB_PATH,
    DEFAULT_CUT_LAYERS,
    DEFAULT_DRAW_LAYERS,
    DXF_DIR,
)
from src.models import DXFFeatures


def _calculate_bulge_arc_length(p1: Tuple[float, float], p2: Tuple[float, float], bulge: float) -> float:
    """Oblicza długość łuku polilinii dla danego wskaźnika wybrzuszenia (bulge)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-6 or abs(bulge) < 1e-6:
        return chord

    theta = 4.0 * math.atan(abs(bulge))
    radius = chord / (2.0 * math.sin(theta / 2.0))
    return radius * theta


def extract_product_code_from_filename(filename: str) -> str:
    """Wyciąga kod produktu z nazwy pliku DXF (usuwa prefiks AI i sufiks _N)."""
    base = os.path.basename(filename)
    if base.lower().endswith(".dxf"):
        base = base[:-4]

    if base.startswith("AI"):
        base = base[2:]

    code = base.split("_")[0].split(" ")[0].strip()
    return code


# Maska nazwy pliku dopuszczanego do zapisu w bazie rysunków:
# prefix „AI” + kod produktu w formacie XXX-YYYY-ZZZ (cyfry), dalej dowolny sufiks.
_UPLOAD_FILENAME_RE = re.compile(r"^AI\d{3}-\d{4}-\d{3}")


def is_valid_upload_filename(filename: str) -> bool:
    """
    Sprawdza, czy nazwa pliku DXF nadaje się do zapisu w bazie rysunków.

    Wymagana maska prefixu: ``AIxxx-xxxx-xxx`` (np. ``AI029-0421-013.dxf``).
    Dalsza część nazwy (rozszerzenie, sufiksy typu ``_1``, ``_3szt``) jest
    dowolna. Sprawdzenie jest wrażliwe na wielkość liter — prefix musi być
    dokładnie ``AI``.

    :param filename: nazwa pliku bez ścieżki (np. ``AI029-0421-013.dxf``).
    :return: True jeśli nazwa przechodzi walidację, False w przeciwnym razie.
    """
    return bool(_UPLOAD_FILENAME_RE.match(filename or ""))


class DXFProcessor:
    """Ekstraktor parametrów geometrycznych z plików DXF."""

    def __init__(
        self,
        cut_layers: Optional[Set[str]] = None,
        draw_layers: Optional[Set[str]] = None,
    ):
        self.cut_layers = {layer.upper() for layer in (cut_layers or DEFAULT_CUT_LAYERS)}
        self.draw_layers = {layer.upper() for layer in (draw_layers or DEFAULT_DRAW_LAYERS)}

    def extract_features(self, file_path: Union[str, Path]) -> DXFFeatures:
        """Główna funkcja wyciągająca cechy geometryczne z pliku DXF (wartości surowe)."""
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Plik DXF nie istnieje: {path_obj}")

        doc = ezdxf.readfile(str(path_obj))
        msp = doc.modelspace()

        entities = list(msp)
        if not entities:
            for layout in doc.layouts:
                if layout.name != "Model":
                    entities.extend(list(layout))

        layers_found = sorted(list({e.dxf.layer for e in entities if hasattr(e.dxf, "layer")}))
        has_cut_layer = any(l.upper() in self.cut_layers for l in layers_found)

        all_x: List[float] = []
        all_y: List[float] = []
        cut_length_mm = 0.0
        draw_length_mm = 0.0
        contours_count = 0

        for entity in entities:
            dxftype = entity.dxftype()
            layer = entity.dxf.layer.upper() if hasattr(entity.dxf, "layer") else "0"

            is_cut = (layer in self.cut_layers) if has_cut_layer else True
            is_draw = layer in self.draw_layers

            if dxftype == "LINE":
                contours_count += 1
                p1 = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                p2 = (float(entity.dxf.end.x), float(entity.dxf.end.y))
                length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                all_x.extend([p1[0], p2[0]])
                all_y.extend([p1[1], p2[1]])
                if is_cut:
                    cut_length_mm += length
                elif is_draw:
                    draw_length_mm += length

            elif dxftype == "CIRCLE":
                contours_count += 1
                r = float(entity.dxf.radius)
                cx, cy = float(entity.dxf.center.x), float(entity.dxf.center.y)
                all_x.extend([cx - r, cx + r])
                all_y.extend([cy - r, cy + r])
                circ = 2.0 * math.pi * r
                if is_cut:
                    cut_length_mm += circ
                elif is_draw:
                    draw_length_mm += circ

            elif dxftype == "ARC":
                contours_count += 1
                r = float(entity.dxf.radius)
                cx, cy = float(entity.dxf.center.x), float(entity.dxf.center.y)
                all_x.extend([cx - r, cx + r])
                all_y.extend([cy - r, cy + r])
                start_angle = float(entity.dxf.start_angle)
                end_angle = float(entity.dxf.end_angle)
                angle_diff = (end_angle - start_angle) % 360.0
                arc_len = (angle_diff / 360.0) * (2.0 * math.pi * r)
                if is_cut:
                    cut_length_mm += arc_len
                elif is_draw:
                    draw_length_mm += arc_len

            elif dxftype == "LWPOLYLINE":
                contours_count += 1
                points = entity.get_points()
                is_closed = bool(entity.closed)
                num_pts = len(points)
                if num_pts > 0:
                    for pt in points:
                        all_x.append(float(pt[0]))
                        all_y.append(float(pt[1]))
                    poly_len = 0.0
                    limit = num_pts if is_closed else num_pts - 1
                    for i in range(limit):
                        p1 = points[i]
                        p2 = points[(i + 1) % num_pts]
                        bulge = p1[4] if len(p1) > 4 else 0.0
                        if abs(bulge) > 1e-6:
                            seg_len = _calculate_bulge_arc_length((p1[0], p1[1]), (p2[0], p2[1]), bulge)
                        else:
                            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                        poly_len += seg_len
                    if is_cut:
                        cut_length_mm += poly_len
                    elif is_draw:
                        draw_length_mm += poly_len

            elif dxftype == "POLYLINE":
                contours_count += 1
                vertices = list(entity.vertices)
                is_closed = bool(entity.is_closed)
                num_v = len(vertices)
                if num_v > 0:
                    for v in vertices:
                        all_x.append(float(v.dxf.location.x))
                        all_y.append(float(v.dxf.location.y))
                    poly_len = 0.0
                    limit = num_v if is_closed else num_v - 1
                    for i in range(limit):
                        v1 = vertices[i]
                        v2 = vertices[(i + 1) % num_v]
                        p1 = (v1.dxf.location.x, v1.dxf.location.y)
                        p2 = (v2.dxf.location.x, v2.dxf.location.y)
                        bulge = getattr(v1.dxf, "bulge", 0.0)
                        if abs(bulge) > 1e-6:
                            seg_len = _calculate_bulge_arc_length(p1, p2, bulge)
                        else:
                            seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                        poly_len += seg_len
                    if is_cut:
                        cut_length_mm += poly_len
                    elif is_draw:
                        draw_length_mm += poly_len

            elif dxftype == "ELLIPSE":
                contours_count += 1
                a = float(entity.dxf.major_axis.magnitude)
                b = a * float(entity.dxf.ratio)
                cx, cy = float(entity.dxf.center.x), float(entity.dxf.center.y)
                all_x.extend([cx - a, cx + a])
                all_y.extend([cy - b, cy + b])
                ell_len = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
                if is_cut:
                    cut_length_mm += ell_len
                elif is_draw:
                    draw_length_mm += ell_len

        if all_x and all_y:
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            width_mm = max_x - min_x
            height_mm = max_y - min_y
        else:
            width_mm, height_mm = 0.0, 0.0

        area_m2 = (width_mm * height_mm) / 1_000_000.0
        aspect_ratio = (width_mm / height_mm) if height_mm > 0 else 0.0
        cut_len_m = cut_length_mm / 1000.0
        draw_len_m = draw_length_mm / 1000.0

        return DXFFeatures(
            filename=path_obj.name,
            bounding_box_width_mm=round(width_mm, 2),
            bounding_box_height_mm=round(height_mm, 2),
            bounding_box_area_m2=round(area_m2, 4),
            total_cut_length_m=round(cut_len_m, 3),
            drawing_length_m=round(draw_len_m, 3),
            contours_count=contours_count,
            layers_found=layers_found,
            aspect_ratio=round(aspect_ratio, 3),
            filenames_all=[path_obj.name],
            files_count=1,
        )


def _merge_features_for_same_code(features_list: List[DXFFeatures]) -> DXFFeatures:
    """
    Scala cechy wielu plików o tym samym kodzie produktu (różne materiały).
    Długości cięcia i rysowania się sumują; bounding box = union.
    """
    if not features_list:
        raise ValueError("Pusta lista cech do scalenia.")
    if len(features_list) == 1:
        return features_list[0]

    max_width = max(f.bounding_box_width_mm for f in features_list)
    max_height = max(f.bounding_box_height_mm for f in features_list)
    total_cut = sum(f.total_cut_length_m for f in features_list)
    total_draw = sum(f.drawing_length_m for f in features_list)
    total_contours = sum(f.contours_count for f in features_list)
    all_layers = sorted({layer for f in features_list for layer in f.layers_found})
    filenames_all = [f.filename for f in features_list]

    area_m2 = (max_width * max_height) / 1_000_000.0
    aspect_ratio = (max_width / max_height) if max_height > 0 else 0.0

    return DXFFeatures(
        filename=features_list[0].filename,
        bounding_box_width_mm=round(max_width, 2),
        bounding_box_height_mm=round(max_height, 2),
        bounding_box_area_m2=round(area_m2, 4),
        total_cut_length_m=round(total_cut, 3),
        drawing_length_m=round(total_draw, 3),
        contours_count=total_contours,
        layers_found=all_layers,
        aspect_ratio=round(aspect_ratio, 3),
        filenames_all=filenames_all,
        files_count=len(features_list),
    )


def index_dxf_directory_to_db(dxf_dir: Union[str, Path] = DXF_DIR, db_path: Union[str, Path] = DB_PATH) -> int:
    """
    Indeksuje wszystkie pliki DXF z katalogu. Pliki o tym samym kodzie produktu
    są grupowane i SUMOWANE (długości cięcia).

    UWAGA: usuwa starą tabelę product_dxf_features przed utworzeniem nowej,
    aby wymusić aktualny schemat (12 kolumn).
    """
    dxf_folder = Path(dxf_dir)
    db_file = Path(db_path)
    if not dxf_folder.exists() or not db_file.exists():
        return 0

    processor = DXFProcessor()
    dxf_files = [f for f in dxf_folder.iterdir() if f.suffix.lower() == ".dxf"]
    print(f"🔄 Indeksowanie {len(dxf_files)} plików DXF do bazy SQLite...")

    conn = sqlite3.connect(db_file)
    indexed_count = 0
    errors: List[Tuple[str, str]] = []

    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS product_dxf_features;")
        cursor.execute("""
            CREATE TABLE product_dxf_features (
                product_code TEXT PRIMARY KEY,
                filename TEXT,
                filenames_json TEXT,
                files_count INTEGER,
                bounding_box_width_mm REAL,
                bounding_box_height_mm REAL,
                bounding_box_area_m2 REAL,
                total_cut_length_m REAL,
                drawing_length_m REAL,
                contours_count INTEGER,
                aspect_ratio REAL,
                layers_json TEXT
            );
        """)

        groups: Dict[str, List[DXFFeatures]] = {}
        for f in dxf_files:
            try:
                code = extract_product_code_from_filename(f.name)
                features = processor.extract_features(f)
                groups.setdefault(code, []).append(features)
            except Exception as e:
                errors.append((f.name, str(e)))

        records = []
        for code, features_list in groups.items():
            merged = _merge_features_for_same_code(features_list)
            records.append((
                code,
                merged.filename,
                json.dumps(merged.filenames_all, ensure_ascii=False),
                merged.files_count,
                merged.bounding_box_width_mm,
                merged.bounding_box_height_mm,
                merged.bounding_box_area_m2,
                merged.total_cut_length_m,
                merged.drawing_length_m,
                merged.contours_count,
                merged.aspect_ratio,
                json.dumps(merged.layers_found, ensure_ascii=False),
            ))

        cursor.executemany(
            "INSERT OR REPLACE INTO product_dxf_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            records,
        )
        conn.commit()
        indexed_count = len(records)

        print(f"✅ Zaindeksowano {indexed_count} unikalnych kodów produktu (z {len(dxf_files)} plików DXF).")
        multi_file_codes = sum(1 for fl in groups.values() if len(fl) > 1)
        if multi_file_codes:
            print(f"   ℹ️ {multi_file_codes} kodów ma wiele plików (sumy długości cięcia).")

        if errors:
            print(f"⚠️ Nie udało się zaindeksować {len(errors)} plików DXF:")
            for name, err in errors[:10]:
                print(f"   • {name}: {err}")
            if len(errors) > 10:
                print(f"   ... i {len(errors) - 10} więcej.")
    finally:
        conn.close()

    return indexed_count


def get_product_dxf_features(product_code: str, db_path: Union[str, Path] = DB_PATH) -> Optional[DXFFeatures]:
    """Pobiera zaindeksowane cechy DXF danego produktu z bazy SQLite."""
    db_file = Path(db_path)
    if not db_file.exists():
        return None

    conn = sqlite3.connect(db_file)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT filename, filenames_json, files_count,
                       bounding_box_width_mm, bounding_box_height_mm,
                       bounding_box_area_m2, total_cut_length_m, drawing_length_m,
                       contours_count, layers_json, aspect_ratio
                FROM product_dxf_features
                WHERE product_code = ?;
            """, (product_code,))
        except sqlite3.OperationalError:
            # Tabela jeszcze nie istnieje (świeża baza, bez indeksacji DXF).
            return None

        row = cursor.fetchone()
        if not row:
            return None

        try:
            filenames_all = json.loads(row[1]) if row[1] else [row[0]]
        except json.JSONDecodeError:
            filenames_all = [row[0]] if row[0] else []

        return DXFFeatures(
            filename=row[0] or "",
            filenames_all=filenames_all,
            files_count=int(row[2]) if row[2] is not None else 1,
            bounding_box_width_mm=float(row[3]),
            bounding_box_height_mm=float(row[4]),
            bounding_box_area_m2=float(row[5]),
            total_cut_length_m=float(row[6]),
            drawing_length_m=float(row[7]),
            contours_count=int(row[8]),
            layers_found=json.loads(row[9]) if row[9] else [],
            aspect_ratio=float(row[10]),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ekstrakcja cech geometrycznych z pliku DXF.")
    parser.add_argument("dxf_path", type=str, help="Ścieżka do pliku DXF.")
    parser.add_argument("--index-all", action="store_true", help="Zaindeksuj wszystkie pliki z katalogu dxf/.")
    args = parser.parse_args()

    if args.index_all:
        index_dxf_directory_to_db()

    processor = DXFProcessor()
    feat = processor.extract_features(args.dxf_path)

    print("=" * 60)
    print(f"📐 ANALIZA PLIKU DXF (wartości surowe, skala 1:10): {args.dxf_path}")
    print("=" * 60)
    print(f"• Wymiary gabarytowe: {feat.bounding_box_width_mm:.2f} mm x {feat.bounding_box_height_mm:.2f} mm")
    print(f"• Pole otaczające:    {feat.bounding_box_area_m2:.4f} m²")
    print(f"• Długość cięcia:     {feat.total_cut_length_m:.3f} m")
    print(f"• Długość rysowania:  {feat.drawing_length_m:.3f} m")
    print(f"• Liczba konturów:    {feat.contours_count}")
    print(f"• Proporcje (Aspect): {feat.aspect_ratio:.2f}")
    print(f"• Wykryte warstwy:    {', '.join(feat.layers_found)}")
    print("=" * 60)