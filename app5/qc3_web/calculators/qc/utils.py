import configparser
import os
from datetime import datetime
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd

# ----------------------------------------------------------------------
# Funkcje pomocnicze (ładowanie konfiguracji, parsowanie rozmiaru)
# ----------------------------------------------------------------------
def load_config():
    config = configparser.ConfigParser()
    config.read('qc_config.ini')
    return config

def parse_pallet_size(size_str):
    """Zwraca (długość, szerokość, wysokość) jako int."""
    try:
        parts = size_str.split('x')
        return int(parts[0]), int(parts[1]), int(parts[2])
    except:
        return 0, 0, 0

# ----------------------------------------------------------------------
# Główne obliczenia (identyczne jak w oryginalnym kodzie)
# ----------------------------------------------------------------------
def calculate_all(form_data):
    config = load_config()
    # Mapa typów palet na klucze w configu
    pallet_weight_map = {
        'PLL EURO': float(config['Weights']['pallet_euro']),
        'PLL #': float(config['Weights']['pallet_industrial']),
        'PLL Specj.': float(config['Weights']['pallet_special']),
        'ROLL': float(config['Weights']['pallet_roll']),
        'PCKG Paczka': float(config['Weights']['pallet_package']),
        'PLL ½': float(config['Weights']['pallet_half']),
        'EURO Karton': float(config['Weights']['pallet_euro_carton']),
        'PLL # Karton': float(config['Weights']['pallet_ind_carton']),
    }
    palette_weight = pallet_weight_map.get(form_data['pallet_type'], 25.0)
    extension_weight = float(config['Weights']['extension'])

    extensions = int(form_data['extensions'])
    cartons = int(form_data['cartons'])
    products = int(form_data['products'])
    max_per = int(form_data['max_per_pallet'])
    unit_weight = float(form_data['unit_weight'])
    length, width, height = parse_pallet_size(form_data['pallet_size'])

    # Obliczenia dla pojedynczej palety
    if cartons > 0:
        items_on_pallet = min(cartons, max_per)
        single_pallet_weight = palette_weight + (extensions * extension_weight) + (unit_weight * items_on_pallet)
    elif products > 0:
        items_on_pallet = products
        single_pallet_weight = palette_weight + (extensions * extension_weight) + (unit_weight * products)
    else:
        items_on_pallet = 0
        single_pallet_weight = palette_weight + (extensions * extension_weight)

    # Obliczenia dla wszystkich palet
    if cartons > 0:
        full_pallets = cartons // max_per
        remainder = cartons % max_per
        full_pallet_weight = palette_weight + (extensions * extension_weight) + (unit_weight * max_per)
    elif products > 0:
        full_pallets = 1
        remainder = 0
        full_pallet_weight = single_pallet_weight
    else:
        full_pallets = 1 if extensions > 0 else 0
        remainder = 0
        full_pallet_weight = single_pallet_weight

    partial_pallet_weight = 0
    if remainder > 0:
        partial_pallet_weight = palette_weight + (extensions * extension_weight) + (unit_weight * remainder)

    total_weight_all = (full_pallets * full_pallet_weight) + (partial_pallet_weight if remainder > 0 else 0)

    return {
        'palette_weight': round(palette_weight, 2),
        'extension_weight': round(extension_weight, 2),
        'single_pallet_weight': round(single_pallet_weight, 2),
        'full_pallets': full_pallets,
        'remainder': remainder,
        'full_pallet_weight': round(full_pallet_weight, 2),
        'partial_pallet_weight': round(partial_pallet_weight, 2),
        'total_weight_all': round(total_weight_all, 2),
        'pallet_length': length,
        'pallet_width': width,
        'pallet_height': height,
        'items_on_pallet': items_on_pallet,
        'unit_weight': unit_weight,
    }

# ----------------------------------------------------------------------
# Generowanie PDF (na podstawie oryginalnego create_pdf)
# ----------------------------------------------------------------------
def generate_pdf(report_data, calculations):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )
    story = []
    styles = getSampleStyleSheet()

    # Próba rejestracji czcionek z folderu fonts
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'fonts/arialbd.ttf'))
        FONT_NAME = 'Arial'
        FONT_BOLD = 'Arial-Bold'
    except:
        FONT_NAME = 'Helvetica'
        FONT_BOLD = 'Helvetica-Bold'

    # Style
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontName=FONT_BOLD, fontSize=9)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=9)
    small_style = ParagraphStyle('SmallStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=8)
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=9,
        textColor=colors.HexColor('#000080'),
        spaceAfter=6
    )
    separator_style = ParagraphStyle(
        'SeparatorStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        textColor=colors.HexColor('#000080')
    )

    # Logo (jeśli istnieje)
    logo_path = os.path.join('static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=4*cm, height=1.2*cm)
            logo_table = Table([[logo]], colWidths=[15*cm])
            logo_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'RIGHT')]))
            story.append(logo_table)
            story.append(Spacer(1, 0.3*cm))
        except Exception as e:
            print(f"Błąd ładowania logo: {e}")

    story.append(Paragraph("_" * 90, separator_style))
    story.append(Spacer(1, 0.3*cm))

    # 1. Informacje podstawowe
    info_data = [
        [Paragraph("Numer produktu:", bold_style), Paragraph(report_data['product_number'], normal_style)],
        [Paragraph("Data kontroli:", bold_style), Paragraph(datetime.now().strftime('%d.%m.%Y %H:%M'), normal_style)],
        [Paragraph("Kontroler:", bold_style), Paragraph(report_data['reporter'], normal_style)],
        [Paragraph("Kierunek wysyłki:", bold_style), Paragraph(report_data['shipping_direction'], normal_style)]
    ]
    info_table = Table(info_data, colWidths=[4*cm, 11*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # 2. Specyfikacja techniczna
    story.append(Paragraph("Specyfikacja techniczna:", section_style))
    story.append(Spacer(1, 0.4*cm))

    cert_notes = {"TAK": "Wymaga dokumentu certyfikatu", "NIE": "Standardowa"}
    stack_notes = {"płasko": "Standardowe", "rolowanie": "Wymaga zabezpieczenia"}

    size_display = report_data['pallet_size']
    if calculations['pallet_length'] > 0:
        size_display = f"{calculations['pallet_length']}x{calculations['pallet_width']}x{calculations['pallet_height']} mm"

    tech_data = [
        [Paragraph("Rodzaj palety", bold_style), Paragraph(report_data['pallet_type'], normal_style), Paragraph("", normal_style)],
        [Paragraph("Paleta certyfikowana", bold_style), Paragraph(report_data['certified'], normal_style),
         Paragraph(cert_notes.get(report_data['certified'], ""), small_style)],
        [Paragraph("Rozmiar palety", bold_style), Paragraph(size_display, normal_style), Paragraph("", normal_style)],
        [Paragraph("Ilość nadstawek", bold_style), Paragraph(f"{report_data['extensions']} szt.", normal_style),
         Paragraph(f"Waga: {calculations['extension_weight']} kg/szt.", small_style)],
        [Paragraph("Rodzaj układania", bold_style), Paragraph(report_data['stack_type'], normal_style),
         Paragraph(stack_notes.get(report_data['stack_type'], ""), small_style)],
        [Paragraph("Waga palety", bold_style), Paragraph(f"{calculations['palette_weight']} kg", normal_style), Paragraph("", normal_style)]
    ]
    tech_table = Table(tech_data, colWidths=[4*cm, 4*cm, 7*cm])
    tech_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 0.4*cm))

    # 3. Dane produktu
    story.append(Paragraph("Dane produktu:", section_style))
    story.append(Spacer(1, 0.4*cm))

    weight_display = str(report_data['unit_weight']).replace('.', ',')
    product_data = [
        [Paragraph("Waga jednej sztuki", bold_style), Paragraph(f"{weight_display} kg", normal_style), Paragraph("", normal_style)],
    ]
    if report_data['cartons'] > 0:
        product_data.append([
            Paragraph("Ilość kartonów", bold_style),
            Paragraph(f"{report_data['cartons']} szt.", normal_style),
            Paragraph("", normal_style)
        ])
        product_data.append([
            Paragraph("Maks. na palecie", bold_style),
            Paragraph(f"{report_data['max_per_pallet']} szt.", normal_style),
            Paragraph("", normal_style)
        ])
    else:
        product_data.append([
            Paragraph("Ilość produktów", bold_style),
            Paragraph(f"{report_data['products']} szt.", normal_style),
            Paragraph("(produkty luzem)", small_style)
        ])

    product_table = Table(product_data, colWidths=[4*cm, 4*cm, 7*cm])
    product_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(product_table)
    story.append(Spacer(1, 0.4*cm))

    # 4. Obliczenia
    story.append(Paragraph("Obliczenia:", section_style))
    story.append(Spacer(1, 0.4*cm))

    weight_for_formula = str(calculations['unit_weight']).replace('.', ',')

    if report_data['cartons'] > 0:
        items_on_pallet = min(report_data['cartons'], report_data['max_per_pallet'])
        calc_formula = f"{calculations['palette_weight']} + ({report_data['extensions']} × {calculations['extension_weight']}) + ({weight_for_formula} × {items_on_pallet})"
        items_label = "kartonów"
    elif report_data['products'] > 0:
        items_on_pallet = report_data['products']
        calc_formula = f"{calculations['palette_weight']} + ({report_data['extensions']} × {calculations['extension_weight']}) + ({weight_for_formula} × {items_on_pallet})"
        items_label = "produktów"
    else:
        calc_formula = f"{calculations['palette_weight']} + ({report_data['extensions']} × {calculations['extension_weight']})"
        items_label = ""

    if items_label:
        calc_data = [
            [Paragraph("Wzór", bold_style),
             Paragraph(f"Waga palety + (nadstawki × waga nadstawki) + (waga sztuki × ilość {items_label})", normal_style),
             Paragraph("", normal_style)],
        ]
    else:
        calc_data = [
            [Paragraph("Wzór", bold_style),
             Paragraph("Waga palety + (nadstawki × waga nadstawki)", normal_style),
             Paragraph("", normal_style)],
        ]

    calc_data.append([
        Paragraph("Podstawienie", bold_style),
        Paragraph(calc_formula, normal_style),
        Paragraph("", normal_style)
    ])

    weight_cell = Paragraph(f"{calculations['single_pallet_weight']} kg", bold_style)

    if report_data['cartons'] > 0:
        if calculations['full_pallets'] > 0:
            calc_data.append([
                Paragraph("Waga pojedynczej palety", bold_style),
                weight_cell,
                Paragraph(f"Pełnych palet: {calculations['full_pallets']}", normal_style)
            ])
        else:
            calc_data.append([
                Paragraph("Waga pojedynczej palety", bold_style),
                weight_cell,
                Paragraph("", normal_style)
            ])

        if calculations['remainder'] > 0:
            calc_data.append([
                Paragraph("Niepełna paleta", bold_style),
                Paragraph(f"{calculations['remainder']} kartonów", normal_style),
                Paragraph(f"Waga: {calculations['partial_pallet_weight']} kg", normal_style)
            ])
    elif report_data['products'] > 0:
        calc_data.append([
            Paragraph("Waga palety z produktami", bold_style),
            weight_cell,
            Paragraph(f"Palet z produktami luzem: {calculations['full_pallets']}", normal_style)
        ])
    else:
        calc_data.append([
            Paragraph("Waga pustej palety", bold_style),
            weight_cell,
            Paragraph(f"Pustych palet: {calculations['full_pallets']}", normal_style)
        ])

    if report_data['cartons'] > 0 or report_data['products'] > 0 or calculations['full_pallets'] > 0:
        calc_data.append([
            Paragraph("Łączna waga", bold_style),
            Paragraph(f"{calculations['total_weight_all']} kg", bold_style),
            Paragraph("", normal_style)
        ])

    calc_table = Table(calc_data, colWidths=[4*cm, 7*cm, 4*cm])
    calc_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(calc_table)
    story.append(Spacer(1, 0.4*cm))

    # 5. Uwagi
    notes = []
    if report_data['shipping_direction'] == "Poza UE":
        notes.append("• Wymagane dodatkowe dokumenty celne")
    if report_data['certified'] == "NIE":
        notes.append("• Paleta nie jest certyfikowana - do transportu wewnętrznego")
    if report_data['stack_type'] == "rolowanie":
        notes.append("• Wymagane dodatkowe zabezpieczenie przed przetoczeniem")
    if report_data['extensions'] > 0:
        notes.append(f"• Uwaga na wysokość z {report_data['extensions']} nadstawkami")
    if report_data['cartons'] == 0 and report_data['products'] > 0:
        notes.append("• Paleta z produktami luzem (bez kartonów)")
    elif report_data['cartons'] == 0 and report_data['products'] == 0:
        notes.append("• Paleta pusta (bez zawartości)")

    if notes:
        story.append(Paragraph("Uwagi:", section_style))
        story.append(Spacer(1, 0.4*cm))
        for note in notes:
            story.append(Paragraph(note, small_style))
            story.append(Spacer(1, 0.1*cm))

    # 6. Stopka
    story.append(Spacer(1, 0.8*cm))
    footer_data = [
        [Paragraph("", normal_style), Paragraph("", normal_style), Paragraph("", normal_style)],
        [Paragraph("Data wygenerowania:", normal_style),
         Paragraph(datetime.now().strftime('%d.%m.%Y %H:%M'), normal_style),
         Paragraph("", normal_style)],
        [Paragraph("Osoba odpowiedzialna:", normal_style),
         Paragraph(report_data['reporter'], normal_style),]
    ]
    footer_table = Table(footer_data, colWidths=[5*cm, 6*cm, 4*cm])
    footer_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))
    story.append(footer_table)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ----------------------------------------------------------------------
# Eksport do Excel (dla listy raportów)
# ----------------------------------------------------------------------
def export_reports_to_excel(reports):
    """reports – lista słowników (lub sqlite3.Row)"""
    output = io.BytesIO()
    data = []
    for r in reports:
        data.append({
            'ID': r['id'],
            'Numer produktu': r['product_number'],
            'Data raportu': r['report_date'],
            'Kontroler': r['reporter'],
            'Kierunek wysyłki': r['shipping_direction'],
            'Rodzaj palety': r['pallet_type'],
            'Certyfikowana': r['certified'],
            'Rozmiar palety': r['pallet_size'],
            'Nadstawki': r['extensions'],
            'Układanie': r['stack_type'],
            'Kartony': r['cartons'],
            'Produkty': r['products'],
            'Max na palecie': r['max_per_pallet'],
            'Waga sztuki': r['unit_weight'],
            'Waga palety': r['single_pallet_weight'],
            'Pełnych palet': r['full_pallets'],
            'Reszta': r['remainder'],
            'Waga pełnej': r['full_pallet_weight'],
            'Waga niepełnej': r['partial_pallet_weight'],
            'Łączna waga': r['total_weight_all'],
            'Ścieżka PDF': r['pdf_path'],
            'Utworzono': r['created_at']
        })
    df = pd.DataFrame(data)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Raporty', index=False)
    output.seek(0)
    return output

def export_statistics_to_excel(statistics):
    output = io.BytesIO()
    data = []
    for s in statistics:
        data.append({
            'Kontroler': s['reporter'],
            'Produkt': s['product_number'],
            'Liczba raportów': s['total_reports'],
            'Łączne kartony': s['total_cartons'] or 0,
            'Łączne pełne palety': s['total_full_pallets'] or 0,
            'Łączna waga': s['total_weight'] or 0
        })
    # Dodaj wiersz sum
    if data:
        total_reports = sum(d['Liczba raportów'] for d in data)
        total_cartons = sum(d['Łączne kartony'] for d in data)
        total_pallets = sum(d['Łączne pełne palety'] for d in data)
        total_weight = sum(d['Łączna waga'] for d in data)
        data.append({
            'Kontroler': 'RAZEM',
            'Produkt': '',
            'Liczba raportów': total_reports,
            'Łączne kartony': total_cartons,
            'Łączne pełne palety': total_pallets,
            'Łączna waga': total_weight
        })
    df = pd.DataFrame(data)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Statystyki', index=False)
    output.seek(0)
    return output