# pdf_report.py
"""
Generator karty akceptacji PDF (produkt → wersje → akceptacje).

Wersja z obsługą akceptacji „Administrator za rolę":
  - kolumny on_behalf_of / acted_by_name są respektowane w tabelach i podpisach.
"""
from io import BytesIO
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, 'fonts')
LOGO_PATH = os.path.join(FONTS_DIR, 'logo_hansa.png')
LOCAL_TZ = ZoneInfo('Europe/Warsaw')


def _register_fonts():
    regular_candidates = [('DejaVuSans.ttf', 'AppFont'), ('arial.ttf', 'AppFont')]
    bold_candidates = [('DejaVuSans-Bold.ttf', 'AppFont-Bold'), ('arialbd.ttf', 'AppFont-Bold')]

    def _try(candidates):
        for filename, name in candidates:
            path = os.path.join(FONTS_DIR, filename)
            if os.path.isfile(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
                except Exception as exc:
                    print(f'[pdf_report] Błąd {path}: {exc}')
        return None

    regular = _try(regular_candidates)
    if regular is None:
        raise RuntimeError(f'Brak czcionki w {FONTS_DIR}.')
    bold = _try(bold_candidates) or regular
    pdfmetrics.registerFontFamily('AppFont', normal=regular, bold=bold,
                                  italic=regular, boldItalic=bold)
    return regular, bold


FONT_REGULAR, FONT_BOLD = _register_fonts()

_LOGO_READER = None
_LOGO_SIZE = None
_LOGO_TRIED = False


def _load_logo():
    global _LOGO_READER, _LOGO_SIZE, _LOGO_TRIED
    if _LOGO_TRIED:
        return _LOGO_READER, _LOGO_SIZE
    _LOGO_TRIED = True
    if not os.path.isfile(LOGO_PATH):
        return None, None
    try:
        _LOGO_READER = ImageReader(LOGO_PATH)
        _LOGO_SIZE = _LOGO_READER.getSize()
        return _LOGO_READER, _LOGO_SIZE
    except Exception:
        return None, None


def _to_local(value):
    if not value:
        return '—'
    try:
        s = str(value).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(LOCAL_TZ).strftime('%d.%m.%Y %H:%M')
    except (ValueError, AttributeError):
        return str(value)


def _safe(v, dash='—'):
    if v is None:
        return dash
    s = str(v).strip()
    return s if s else dash


def _to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except (TypeError, ValueError):
        return {}


def _approver_cell(a):
    """
    Buduje tekst przedstawiciela:
    - zwykła akceptacja: 'Imię Nazwisko'
    - admin za rolę: 'Imię Nazwisko (Administrator za: ROLA)'
    """
    if not a:
        return '—'
    who = _safe(a.get('full_name'))
    if a.get('on_behalf_of'):
        acted = _safe(a.get('acted_by_name') or a.get('full_name'))
        return f'{who} <font color="#6b7280">(Administrator za: {a["on_behalf_of"]}; wykonał: {acted})</font>'
    return who


def generate(product, doc_version, approvals, audit_log, report_id=None):
    product = _to_dict(product)
    doc_version = _to_dict(doc_version)
    approvals = [_to_dict(a) for a in (approvals or [])]
    audit_log = [_to_dict(a) for a in (audit_log or [])]

    generated_at = datetime.now(LOCAL_TZ)
    if not report_id:
        ts = generated_at.strftime('%Y%m%d%H%M%S')
        report_id = f"RPT-{product.get('name', '?')}-V{doc_version.get('version_num', 0):03d}-{ts}"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=36*mm, bottomMargin=20*mm,
    )
    W = doc.width

    navy = colors.HexColor('#1a2744')
    indigo = colors.HexColor('#4f52c7')
    light_bg = colors.HexColor('#eef2ff')
    grey = colors.HexColor('#6b7280')
    light_grey = colors.HexColor('#e5e7eb')
    text_col = colors.HexColor('#111827')
    success = colors.HexColor('#065f46')
    success_bg = colors.HexColor('#d1fae5')

    styles = getSampleStyleSheet()
    banner_style = ParagraphStyle('B', fontName=FONT_BOLD, fontSize=16, leading=20,
                                  textColor=colors.white, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('S', fontName=FONT_REGULAR, fontSize=10, leading=13,
                                    textColor=navy, alignment=TA_CENTER)
    meta_style = ParagraphStyle('M', fontName=FONT_REGULAR, fontSize=8.5, leading=11,
                                textColor=grey, alignment=TA_CENTER)
    section_style = ParagraphStyle('Sec', fontName=FONT_BOLD, fontSize=11, leading=14,
                                   textColor=navy, spaceBefore=10, spaceAfter=4, keepWithNext=True)
    cell_label_style = ParagraphStyle('CL', fontName=FONT_BOLD, fontSize=8.5, leading=11, textColor=navy)
    cell_style = ParagraphStyle('C', fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=text_col)
    cell_muted = ParagraphStyle('CM', fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=grey)
    th_style = ParagraphStyle('TH', fontName=FONT_BOLD, fontSize=8.5, leading=11, textColor=colors.white)

    story = []

    banner = Table([[Paragraph(_safe(product.get('name')), banner_style)]], colWidths=[W])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), indigo),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(banner)
    story.append(Spacer(1, 5))

    story.append(Paragraph(f'Wersja v{int(doc_version.get("version_num", 0)):03d}', subtitle_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f'Raport: {report_id} &nbsp;|&nbsp; Wygenerowano: {generated_at.strftime("%d.%m.%Y %H:%M")} (Europe/Warsaw)',
        meta_style))
    story.append(Spacer(1, 10))

    # 1. INFO
    story.append(Paragraph('1. INFORMACJE O PRODUKCIE', section_style))
    info_rows = [
        [Paragraph('Produkt (nazwa pliku)', cell_label_style), Paragraph(_safe(product.get('name')), cell_style)],
        [Paragraph('Wersja dokumentacji', cell_label_style),
         Paragraph(f'v{int(doc_version.get("version_num", 0)):03d}', cell_style)],
        [Paragraph('Plik źródłowy', cell_label_style), Paragraph(_safe(doc_version.get('original_filename')), cell_style)],
        [Paragraph('Data wersji', cell_label_style), Paragraph(_to_local(doc_version.get('created_at')), cell_style)],
    ]
    info_table = Table(info_rows, colWidths=[50*mm, W - 50*mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), light_bg),
        ('BOX', (0, 0), (-1, -1), 0.5, grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, light_grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6))

    # 2. WERDYKT
    story.append(Paragraph('2. WYNIK AKCEPTACJI', section_style))
    stage1_ok = sorted({a['role'] for a in approvals if a.get('stage') == 1 and a.get('decision') == 'AKCEPTUJE' and a.get('validity') == 'WAZNA'})
    stage2_ok = sorted({a['role'] for a in approvals if a.get('stage') == 2 and a.get('decision') == 'AKCEPTUJE' and a.get('validity') == 'WAZNA'})
    from db import STAGE1_ROLES, STAGE2_ROLES
    complete = len(stage1_ok) >= len(STAGE1_ROLES) and len(stage2_ok) >= len(STAGE2_ROLES)
    if complete:
        verdict_text = 'DOKUMENTACJA ZAAKCEPTOWANA'
        verdict_bg = success_bg
        verdict_fg = success
    else:
        verdict_text = 'PROCES W TOKU'
        verdict_bg = colors.HexColor('#fef3c7')
        verdict_fg = colors.HexColor('#92400e')
    verdict_style = ParagraphStyle('V', fontName=FONT_BOLD, fontSize=13, leading=16, textColor=verdict_fg)
    verdict_table = Table([[Paragraph(verdict_text, verdict_style)]], colWidths=[W])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), verdict_bg),
        ('BOX', (0, 0), (-1, -1), 1, verdict_fg),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 6))

    # 3. ETAP I
    story.append(Paragraph('3. AKCEPTACJE – ETAP I (po 1 przedstawicielu roli)', section_style))
    rows = [[Paragraph('Rola', th_style), Paragraph('Przedstawiciel', th_style),
             Paragraph('Decyzja', th_style), Paragraph('Data', th_style), Paragraph('Komentarz', th_style)]]
    for role in STAGE1_ROLES:
        a = next((x for x in approvals if x.get('stage') == 1 and x.get('role') == role
                  and x.get('validity') == 'WAZNA' and x.get('decision') == 'AKCEPTUJE'), None)
        if a:
            rows.append([
                Paragraph(role, cell_style),
                Paragraph(_approver_cell(a), cell_style),
                Paragraph('<font color="#065f46"><b>Akceptuję</b></font>', cell_style),
                Paragraph(_to_local(a.get('created_at')), cell_style),
                Paragraph(_safe(a.get('comment')), cell_style),
            ])
        else:
            rows.append([
                Paragraph(role, cell_style), Paragraph('—', cell_muted),
                Paragraph('<font color="#92400e">Oczekuje</font>', cell_style),
                Paragraph('—', cell_muted), Paragraph('—', cell_muted),
            ])
    t1 = Table(rows, colWidths=[40*mm, 55*mm, 22*mm, 28*mm, W - 145*mm], repeatRows=1)
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('BOX', (0, 0), (-1, -1), 0.5, grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, light_grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t1)
    story.append(Spacer(1, 6))

    # 4. ETAP II
    story.append(Paragraph('4. AKCEPTACJE – ETAP II (QC + Administrator)', section_style))
    rows = [[Paragraph('Rola', th_style), Paragraph('Osoba', th_style),
             Paragraph('Decyzja', th_style), Paragraph('Data', th_style), Paragraph('Komentarz', th_style)]]
    for role in STAGE2_ROLES:
        a = next((x for x in approvals if x.get('stage') == 2 and x.get('role') == role
                  and x.get('validity') == 'WAZNA' and x.get('decision') == 'AKCEPTUJE'), None)
        if a:
            rows.append([
                Paragraph(role, cell_style),
                Paragraph(_approver_cell(a), cell_style),
                Paragraph('<font color="#065f46"><b>Akceptuję</b></font>', cell_style),
                Paragraph(_to_local(a.get('created_at')), cell_style),
                Paragraph(_safe(a.get('comment')), cell_style),
            ])
        else:
            rows.append([
                Paragraph(role, cell_style), Paragraph('—', cell_muted),
                Paragraph('<font color="#92400e">Oczekuje</font>', cell_style),
                Paragraph('—', cell_muted), Paragraph('—', cell_muted),
            ])
    t2 = Table(rows, colWidths=[40*mm, 55*mm, 22*mm, 28*mm, W - 145*mm], repeatRows=1)
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('BOX', (0, 0), (-1, -1), 0.5, grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, light_grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 6))

    # 5. PODPISY IMIENNE
    story.append(Paragraph('5. PODPISY IMIENNE', section_style))
    for a in approvals:
        if a.get('validity') == 'WAZNA' and a.get('decision') == 'AKCEPTUJE':
            extra = ''
            if a.get('on_behalf_of'):
                acted = _safe(a.get('acted_by_name') or a.get('full_name'))
                extra = (f' — <font color="#92400e">Administrator za: {a["on_behalf_of"]}</font>'
                         f' <font color="#6b7280">(wykonał: {acted})</font>')
            story.append(Paragraph(
                f'Zatwierdzone przez <b>{_safe(a.get("full_name"))}</b> '
                f'<font color="#6b7280">({_safe(a.get("role"))}, Etap {a.get("stage")}, '
                f'{_to_local(a.get("created_at"))})</font>{extra}',
                cell_style))
            story.append(Spacer(1, 2))
    story.append(Spacer(1, 6))

    # 6. HISTORIA
    if audit_log:
        story.append(Paragraph('6. HISTORIA ZDARZEŃ PRODUKTU', section_style))
        rows = [[Paragraph('Data', th_style), Paragraph('Zdarzenie', th_style),
                 Paragraph('Opis', th_style), Paragraph('Kto', th_style)]]
        for h in audit_log:
            rows.append([
                Paragraph(_to_local(h.get('created_at')), cell_style),
                Paragraph(_safe(h.get('event_type')), cell_style),
                Paragraph(_safe(h.get('description')), cell_style),
                Paragraph(_safe(h.get('full_name')), cell_style),
            ])
        th_ = Table(rows, colWidths=[30*mm, 35*mm, W - 105*mm, 40*mm], repeatRows=1)
        th_.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('BOX', (0, 0), (-1, -1), 0.5, grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, light_grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        story.append(th_)

    def _draw_header_footer(canvas, doc_obj):
        canvas.saveState()
        page_w, page_h = A4
        logo_reader, logo_size = _load_logo()
        if logo_reader:
            iw, ih = logo_size
            lh = 25 * mm
            lw = lh * (iw / ih) if ih else lh
            canvas.drawImage(logo_reader, 18*mm, page_h - 5.5*mm - lh,
                             width=lw, height=lh, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(navy)
        canvas.setFont(FONT_BOLD, 11)
        canvas.drawRightString(page_w - 18*mm, page_h - 15*mm, 'KARTA AKCEPTACJI')
        canvas.setFont(FONT_REGULAR, 8)
        canvas.drawRightString(page_w - 18*mm, page_h - 20*mm, 'DOKUMENTACJI TECHNICZNEJ')
        canvas.setStrokeColor(navy)
        canvas.setLineWidth(1)
        canvas.line(18*mm, page_h - 33*mm, page_w - 18*mm, page_h - 33*mm)
        canvas.setFont(FONT_REGULAR, 7.5)
        canvas.setFillColor(grey)
        canvas.setStrokeColor(light_grey)
        canvas.setLineWidth(0.3)
        canvas.line(18*mm, 14*mm, page_w - 18*mm, 14*mm)
        canvas.drawString(18*mm, 9*mm, f'AcceptaDoc — {report_id}')
        canvas.drawRightString(page_w - 18*mm, 9*mm, f'Strona {doc_obj.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)
    return buf.getvalue()