# -*- coding: utf-8 -*-
"""
Flask web app do szacowania czasu kroju na podstawie plików DXF.
Uruchomienie: python app.py
"""

import os
import tempfile
import dxfgrabber
from flask import Flask, render_template, request, flash
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

# Dodaj to po utworzeniu 'app'
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.secret_key = 'twoj_tajny_klucz_zmien_w_produkcji'

# Mnożniki (stałe)
MCKZ = 0.08307067       # Zund – czysty krój
MCKL = 0.090474006      # Lectra – czysty krój
MCKJ = 0.101171631      # Jigwei – czysty krój
MR = 1.08748            # Mnożnik ramki

def oblicz_dlugosc_sciezki(plik_dxf):
    """Oblicza całkowitą długość ścieżki z pliku DXF."""
    dxf = dxfgrabber.readfile(plik_dxf)
    dlugosc = 0.0
    poprzedni_punkt = None

    for entity in dxf.entities:
        if entity.dxftype == 'LINE':
            start = (entity.start.x, entity.start.y)
            end = (entity.end.x, entity.end.y)
            dlugosc += ((end[0] - start[0])**2 + (end[1] - start[1])**2)**0.5
        elif entity.dxftype in ('LWPOLYLINE', 'POLYLINE'):
            for point in entity.points:
                aktualny = (point[0], point[1])
                if poprzedni_punkt:
                    dlugosc += ((aktualny[0] - poprzedni_punkt[0])**2 + (aktualny[1] - poprzedni_punkt[1])**2)**0.5
                poprzedni_punkt = aktualny
            poprzedni_punkt = None
    return dlugosc

def oblicz_czasy(dlugosc, sztuk):
    """Zwraca słownik z obliczonymi czasami."""
    cz = round((((dlugosc * MCKZ) * MR) / 60) / sztuk, 2)
    cl = round((((dlugosc * MCKL) * MR) / 60) / sztuk, 2)
    cw = round((((dlugosc * MCKJ) * MR) / 60) / sztuk, 2)
    ckz = round(((dlugosc * MCKZ) * MR) / 60, 2)
    ckl = round(((dlugosc * MCKL) * MR) / 60, 2)
    ckw = round(((dlugosc * MCKJ) * MR) / 60, 2)
    return {
        'dlugosc': round(dlugosc, 1),
        'cz': cz, 'cl': cl, 'cw': cw,
        'ckz': ckz, 'ckl': ckl, 'ckw': ckw
    }

@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    filename = None
    sztuk = 1  # domyślna wartość dla GET

    if request.method == 'POST':
        # Pobranie wartości z formularza (może być string)
        sztuk_str = request.form.get('sztuk', '1')
        file = request.files.get('file')

        # Walidacja pliku
        if not file or file.filename == '':
            flash('Nie wybrano pliku.', 'error')
            return render_template('index.html', sztuk=sztuk_str)

        # Walidacja liczby sztuk
        try:
            sztuk = int(sztuk_str)
            if sztuk < 1:
                raise ValueError
        except ValueError:
            flash('Liczba sztuk musi być liczbą całkowitą większą od 0.', 'error')
            return render_template('index.html', sztuk=sztuk_str)

        # Zapis tymczasowego pliku
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            dlugosc = oblicz_dlugosc_sciezki(tmp_path)
            results = oblicz_czasy(dlugosc, sztuk)
            filename = os.path.basename(file.filename)
        except Exception as e:
            flash(f'Błąd przetwarzania pliku: {str(e)}', 'error')
            return render_template('index.html', sztuk=sztuk)
        finally:
            os.unlink(tmp_path)

    # Dla GET lub po sukcesie POST
    return render_template('index.html', results=results, filename=filename, sztuk=sztuk)

if __name__ == '__main__':
    app.run(debug=True)