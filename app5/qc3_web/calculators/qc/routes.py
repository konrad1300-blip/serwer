from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify, current_app
from .forms import QcReportForm
from .utils import calculate_all, generate_pdf, export_reports_to_excel, export_statistics_to_excel, load_config
from database.db_handler import DatabaseHandler
import configparser
import os
from datetime import datetime, timedelta


qc_bp = Blueprint('qc', __name__, template_folder='templates', static_folder='static')

# ----------------------------------------------------------------------
# Strona główna kalkulatora – formularz
# ----------------------------------------------------------------------
@qc_bp.route('/', methods=['GET', 'POST'])
def form():
    form = QcReportForm()
    # Wczytaj listę kontrolerów z konfiguracji
    config = load_config()
    controllers = [c.strip() for c in config['Controllers']['controllers'].split(',')]
    form.reporter.choices = [(c, c) for c in controllers]

    # Sprawdź czy trzeba wczytać raport z historii
    load_id = request.args.get('load_id')
    if load_id:
        db = DatabaseHandler(current_app.config['DATABASE'])
        report = db.get_report_by_id(load_id)
        if report:
            # Wypełnij formularz danymi z raportu
            form.product_number.data = report['product_number']
            form.shipping_direction.data = report['shipping_direction']
            form.pallet_type.data = report['pallet_type']
            form.certified.data = report['certified']
            form.pallet_size.data = report['pallet_size']
            form.extensions.data = report['extensions']
            form.cartons.data = report['cartons']
            form.products.data = report['products']
            form.max_per_pallet.data = report['max_per_pallet']
            form.stack_type.data = report['stack_type']
            form.unit_weight.data = report['unit_weight']
            form.reporter.data = report['reporter']
            flash('Wczytano raport z historii. Możesz go edytować i wygenerować nowy PDF.', 'info')

    if request.method == 'POST' and form.validate():
        data = form.data.copy()
        # Dodaj datę raportu
        data['report_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Obliczenia
        calculations = calculate_all(data)
        # Połącz dane
        report_data = {**data, **calculations}
        # Zapisz do bazy
        db = DatabaseHandler(current_app.config['DATABASE'])
        report_id = db.save_report(report_data)
        # Generuj PDF
        pdf_buffer = generate_pdf(report_data, calculations)
        # Zwróć PDF jako odpowiedź
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f'raport_qc_{report_id}.pdf',
            mimetype='application/pdf'
        )

    return render_template('qc/form.html', form=form)

# ----------------------------------------------------------------------
# Endpoint AJAX do dynamicznych obliczeń
# ----------------------------------------------------------------------
@qc_bp.route('/calculate', methods=['POST'])
def calculate_ajax():
    data = request.get_json()
    # Konwersja typów (formularz przysyła stringi)
    # Niektóre pola muszą być liczbami
    try:
        data['extensions'] = int(data.get('extensions', 0))
        data['cartons'] = int(data.get('cartons', 0))
        data['products'] = int(data.get('products', 0))
        data['max_per_pallet'] = int(data.get('max_per_pallet', 1))
        data['unit_weight'] = float(data.get('unit_weight', 0))
    except ValueError:
        return jsonify({'error': 'Nieprawidłowe dane liczbowe'}), 400
    calculations = calculate_all(data)
    return jsonify(calculations)

# ----------------------------------------------------------------------
# Historia raportów
# ----------------------------------------------------------------------
@qc_bp.route('/history')
def history():
    db = DatabaseHandler(current_app.config['DATABASE'])
    reports = db.get_all_reports()
    now = datetime.now()
    start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    return render_template('qc/history.html', 
                           reports=reports, 
                           start_date=start_date, 
                           end_date=end_date)

@qc_bp.route('/history/filters', methods=['GET'])
def history_filters():
    db = DatabaseHandler(current_app.config['DATABASE'])
    controllers = db.get_controllers()
    products = db.get_products()
    return jsonify({'controllers': controllers, 'products': products})

# ----------------------------------------------------------------------
# Filtrowanie historii (AJAX)
# ----------------------------------------------------------------------
@qc_bp.route('/history/filter', methods=['POST'])
def history_filter():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    controller = data.get('controller')
    product = data.get('product')

    db = DatabaseHandler(current_app.config['DATABASE'])
    reports = []

    if start_date and end_date:
        reports = db.get_reports_by_date_range(start_date, end_date)
        if controller and controller != 'Wszyscy':
            reports = [r for r in reports if controller in r['reporter']]
        if product and product != 'Wszystkie':
            reports = [r for r in reports if product in r['product_number']]
    elif controller and controller != 'Wszyscy':
        reports = db.get_reports_by_controller(controller)
    elif product and product != 'Wszystkie':
        reports = db.get_reports_by_product(product)
    else:
        reports = db.get_all_reports()

    # Przygotuj dane do tabeli
    result = []
    for r in reports:
        result.append({
            'id': r['id'],
            'product_number': r['product_number'],
            'report_date': r['report_date'],
            'reporter': r['reporter'],
            'shipping_direction': r['shipping_direction'],
            'pallet_type': r['pallet_type'],
            'certified': r['certified'],
            'unit_weight': f"{r['unit_weight']} kg",
            'single_pallet_weight': f"{r['single_pallet_weight']} kg",
            'cartons': r['cartons'],
            'full_pallets': r['full_pallets'],
            'total_weight_all': f"{r['total_weight_all']} kg"
        })
    return jsonify(result)

# ----------------------------------------------------------------------
# Usuwanie raportu
# ----------------------------------------------------------------------
@qc_bp.route('/history/delete/<int:report_id>', methods=['DELETE'])
def delete_report(report_id):
    db = DatabaseHandler(current_app.config['DATABASE'])
    db.delete_report(report_id)
    return jsonify({'success': True})

# ----------------------------------------------------------------------
# Pobieranie pojedynczego raportu do edycji
# ----------------------------------------------------------------------
@qc_bp.route('/history/get/<int:report_id>', methods=['GET'])
def get_report(report_id):
    db = DatabaseHandler(current_app.config['DATABASE'])
    report = db.get_report_by_id(report_id)
    if report:
        return jsonify({
            'id': report['id'],
            'product_number': report['product_number'],
            'shipping_direction': report['shipping_direction'],
            'pallet_type': report['pallet_type'],
            'certified': report['certified'],
            'pallet_size': report['pallet_size'],
            'extensions': report['extensions'],
            'cartons': report['cartons'],
            'products': report['products'],
            'max_per_pallet': report['max_per_pallet'],
            'stack_type': report['stack_type'],
            'unit_weight': report['unit_weight'],
            'reporter': report['reporter']
        })
    return jsonify({'error': 'Raport nie znaleziony'}), 404

# ----------------------------------------------------------------------
# Statystyki
# ----------------------------------------------------------------------
@qc_bp.route('/statistics')
def statistics():
    db = DatabaseHandler(current_app.config['DATABASE'])
    # Pobierz listę kontrolerów i produktów dla filtrów
    controllers = ['Wszyscy'] + db.get_controllers()
    products = ['Wszystkie'] + db.get_products()
    # Domyślny zakres: ostatnie 30 dni
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template('qc/statistics.html',
                           controllers=controllers,
                           products=products,
                           start_date=start_date,
                           end_date=end_date)

# ----------------------------------------------------------------------
# Filtrowanie statystyk (AJAX)
# ----------------------------------------------------------------------
@qc_bp.route('/statistics/filter', methods=['POST'])
def statistics_filter():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db = DatabaseHandler(current_app.config['DATABASE'])
    stats = db.get_statistics(start_date, end_date)
    # Przekształć na listę słowników
    result = []
    for s in stats:
        result.append({
            'reporter': s['reporter'],
            'product_number': s['product_number'],
            'total_reports': s['total_reports'],
            'total_cartons': s['total_cartons'] or 0,
            'total_full_pallets': s['total_full_pallets'] or 0,
            'total_weight': float(s['total_weight']) if s['total_weight'] else 0
        })
    return jsonify(result)

# ----------------------------------------------------------------------
# Eksport historii do Excel
# ----------------------------------------------------------------------
@qc_bp.route('/export/history', methods=['POST'])
def export_history():
    data = request.get_json() if request.is_json else {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    controller = data.get('controller')
    product = data.get('product')

    db = DatabaseHandler(current_app.config['DATABASE'])
    if start_date and end_date:
        reports = db.get_reports_by_date_range(start_date, end_date)
        if controller and controller != 'Wszyscy':
            reports = [r for r in reports if controller in r['reporter']]
        if product and product != 'Wszystkie':
            reports = [r for r in reports if product in r['product_number']]
    else:
        reports = db.get_all_reports()

    excel_buffer = export_reports_to_excel(reports)
    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=f'historia_qc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ----------------------------------------------------------------------
# Eksport statystyk do Excel
# ----------------------------------------------------------------------
@qc_bp.route('/export/statistics', methods=['POST'])
def export_statistics():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    db = DatabaseHandler(current_app.config['DATABASE'])
    stats = db.get_statistics(start_date, end_date)
    excel_buffer = export_statistics_to_excel(stats)
    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=f'statystyki_qc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ----------------------------------------------------------------------
# Edycja konfiguracji
# ----------------------------------------------------------------------
@qc_bp.route('/config', methods=['GET', 'POST'])
def edit_config():
    config = load_config()
    if request.method == 'POST':
        # Zapisz zmiany
        config['Weights']['pallet_euro'] = request.form['pallet_euro']
        config['Weights']['pallet_industrial'] = request.form['pallet_industrial']
        config['Weights']['pallet_special'] = request.form['pallet_special']
        config['Weights']['pallet_roll'] = request.form['pallet_roll']
        config['Weights']['pallet_package'] = request.form['pallet_package']
        config['Weights']['pallet_half'] = request.form['pallet_half']
        config['Weights']['pallet_euro_carton'] = request.form['pallet_euro_carton']
        config['Weights']['pallet_ind_carton'] = request.form['pallet_ind_carton']
        config['Weights']['extension'] = request.form['extension']
        config['Weights']['default_unit_weight'] = request.form['default_unit_weight']

        config['Controllers']['controllers'] = request.form['controllers']
        config['Controllers']['default_controller'] = request.form['default_controller']

        config['Settings']['default_shipping'] = request.form['default_shipping']
        config['Settings']['default_pallet'] = request.form['default_pallet']
        config['Settings']['default_certified'] = request.form['default_certified']
        config['Settings']['default_size'] = request.form['default_size']
        config['Settings']['default_stack'] = request.form['default_stack']

        with open('qc_config.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        flash('Konfiguracja została zapisana.', 'success')
        return redirect(url_for('qc.edit_config'))

    return render_template('qc/config.html', config=config)