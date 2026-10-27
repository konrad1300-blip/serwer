import os
import sys
import math
import numpy as np
import ezdxf

# Import modułu GUI do okna wyboru pliku
import tkinter as tk
from tkinter import filedialog


def select_file_via_gui() -> str:
    """
    Otwiera okno dialogowe wyboru pliku DXF z dysku.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    selected_path = filedialog.askopenfilename(
        title="Wybierz plik DXF do analizy",
        filetypes=[("Pliki DXF", "*.dxf"), ("Wszystkie pliki", "*.*")]
    )
    root.destroy()
    return selected_path


def extract_product_code(file_path: str) -> str:
    """
    Wyciąga kod produktu z nazwy pliku (indeksy 2 do 14 -> 12 znaków).
    """
    file_name = os.path.basename(file_path)
    return file_name[2:14]


def get_polyline_points(entity):
    """
    Uniwersalna funkcja wyciągająca listę punktów (x, y) z dowolnej polilinii
    (zarówno nowszych LWPOLYLINE, jak i starszych POLYLINE z wierzchołkami VERTEX).
    """
    points = []
    dxftype = entity.dxftype()

    if dxftype == 'LWPOLYLINE':
        # LWPOLYLINE posiada bezpośrednią metodę get_points()
        points = [(p[0], p[1]) for p in entity.get_points()]
    elif dxftype == 'POLYLINE':
        # Starsza POLYLINE zawiera obiekty podrzędne VERTEX
        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        
    return points


def extract_dxf_features(file_path: str) -> dict:
    """
    Główna funkcja wyciągająca cechy geometryczne z plików DXF bazujących na poliliniach.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Plik nie istnieje: {file_path}")

    product_code = extract_product_code(file_path)
    doc = ezdxf.readfile(file_path)
    
    # Pobieramy przestrzeń modelu lub arkuszy
    msp = doc.modelspace()
    entities = list(msp)
    if not entities:
        for layout in doc.layouts:
            if layout.name != 'Model':
                entities.extend(list(layout))

    # Zmienne do zbierania statystyk geometrycznych
    all_x = []
    all_y = []
    total_length = 0.0
    segment_angles = []

    count_line = 0
    count_arc = 0
    count_circle = 0
    count_polyline = 0

    # Iteracja po wszystkich obiektach
    for entity in entities:
        dxftype = entity.dxftype()

        # 1. Obsługa prostych linii (LINE)
        if dxftype == 'LINE':
            count_line += 1
            p1 = (entity.dxf.start.x, entity.dxf.start.y)
            p2 = (entity.dxf.end.x, entity.dxf.end.y)
            
            all_x.extend([p1[0], p2[0]])
            all_y.extend([p1[1], p2[1]])

            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.hypot(dx, dy)
            total_length += length

            if length > 0.001:
                angle = math.degrees(math.atan2(dy, dx)) % 180
                segment_angles.append(angle)

        # 2. Obsługa okręgów i łuków
        elif dxftype == 'CIRCLE':
            count_circle += 1
            r = entity.dxf.radius
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            all_x.extend([cx - r, cx + r])
            all_y.extend([cy - r, cy + r])
            total_length += 2 * math.pi * r

        elif dxftype == 'ARC':
            count_arc += 1
            r = entity.dxf.radius
            cx, cy = entity.dxf.center.x, entity.dxf.center.y
            all_x.extend([cx - r, cx + r])
            all_y.extend([cy - r, cy + r])
            
            # Długość łuku
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            angle_diff = (end_angle - start_angle) % 360
            total_length += (angle_diff / 360.0) * (2 * math.pi * r)

        # 3. Obsługa polilinii (POLYLINE oraz LWPOLYLINE)
        elif dxftype in ('POLYLINE', 'LWPOLYLINE'):
            count_polyline += 1
            pts = get_polyline_points(entity)

            if pts:
                # Zbieranie współrzędnych do wymiarów gabarytowych
                for px, py in pts:
                    all_x.append(px)
                    all_y.append(py)

                # Analiza poszczególnych segmentów polilinii
                is_closed = getattr(entity, 'is_closed', False)
                num_pts = len(pts)

                for i in range(num_pts - 1 if not is_closed else num_pts):
                    p1 = pts[i]
                    p2 = pts[(i + 1) % num_pts]

                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    seg_len = math.hypot(dx, dy)
                    total_length += seg_len

                    if seg_len > 0.001:  # Ignorujemy punkty nakładające się
                        angle = math.degrees(math.atan2(dy, dx)) % 180
                        segment_angles.append(angle)

    # Obliczanie Bounding Boxa na podstawie zgromadzonych wierzchołków
    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        width = max_x - min_x
        height = max_y - min_y
        bbox_area = width * height
        aspect_ratio = width / height if height > 0 else 0.0
    else:
        width, height, bbox_area, aspect_ratio = 0.0, 0.0, 0.0, 0.0

    # Histogram kątów nachylenia krawędzi (8 koszyków)
    if segment_angles:
        angle_hist, _ = np.histogram(segment_angles, bins=8, range=(0, 180), density=True)
    else:
        angle_hist = np.zeros(8)

    features = {
        'file_path': file_path,
        'product_code': product_code,
        'bbox_width': width,
        'bbox_height': height,
        'aspect_ratio': aspect_ratio,
        'bbox_area': bbox_area,
        'total_length': total_length,
        'count_line': count_line,
        'count_arc': count_arc,
        'count_circle': count_circle,
        'count_polyline': count_polyline,
        'angle_histogram': angle_hist.tolist()
    }

    return features


def convert_features_to_vector(features_dict: dict) -> np.ndarray:
    """
    Konwertuje słownik cech numerycznych na macierz NumPy (float32).
    """
    numerical_values = [
        features_dict['bbox_width'],
        features_dict['bbox_height'],
        features_dict['aspect_ratio'],
        features_dict['bbox_area'],
        features_dict['total_length'],
        features_dict['count_line'],
        features_dict['count_arc'],
        features_dict['count_circle'],
        features_dict['count_polyline']
    ]
    numerical_values.extend(features_dict['angle_histogram'])

    return np.array(numerical_values, dtype=np.float32)


if __name__ == "__main__":
    dxf_path = ""
    if len(sys.argv) > 1:
        dxf_path = sys.argv[1]
    else:
        print("Otwieranie okna wyboru pliku...")
        dxf_path = select_file_via_gui()

    if not dxf_path:
        print("Nie wybrano pliku.")
        sys.exit()

    print(f"Wybrany plik: {dxf_path}")

    try:
        data = extract_dxf_features(dxf_path)
        vec = convert_features_to_vector(data)

        print("\n--- OTRZYMANE REALNE DANE GEOMETRYCZNE ---")
        print(f"Kod produktu: {data['product_code']}")
        print(f"Wymiary gabarytowe (X x Y): {data['bbox_width']:.2f} mm x {data['bbox_height']:.2f} mm")
        print(f"Proporcje (Aspect Ratio): {data['aspect_ratio']:.2f}")
        print(f"Całkowita długość krawędzi: {data['total_length']:.2f} mm")
        print(f"Liczba polilinii: {data['count_polyline']}")
        print(f"\nWektor dla sieci neuronowej (kształt {vec.shape}):\n{vec}")

    except Exception as e:
        print(f"Błąd analizy: {e}")