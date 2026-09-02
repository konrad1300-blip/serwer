import csv
import os
from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

app.config['APPLICATION_ROOT'] = '/app9'

CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'materiały.csv')

def load_materials_dict():
    """Wczytuje plik materiały.csv do słownika: {kod_materialu: nazwa_materialu}."""
    materials = {}
    if os.path.exists(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = ';' if ';' in sample else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                if len(row) >= 2:
                    code = row[0].strip().upper()
                    name = row[1].strip()
                    if code:
                        materials[code] = name
    return materials

def remove_polish_chars(input_str):
    """Usuwa polskie 'ogonki', chroniąc systemy operacyjne maszyn krojczych przed błędami."""
    if not input_str:
        return ""
    mapping = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    return "".join(mapping.get(char, char) for char in input_str)

@app.route('/', methods=['GET', 'POST'])
def index():
    wygenerowana_nazwa = ""
    error_message = ""
    material_nazwa_wyswietlana = ""

    form_data = {
        'ilosc_szt': '', 'opis': '', 'material_kod': '', 'dlugosc': '',
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Zu', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()[:10]  # Max 10 znaków
        material_kod = request.form.get('material_kod', '').strip().upper()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Zu')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Walidacja pól wymaganych (wszystkie oprócz opisu)
        if not (ilosc_szt and material_kod and strona and kolor_pisaka and dlugosc and maszyna and kod_produktu):
            error_message = "Proszę uzupełnić wszystkie wymagane pola."
        else:
            # Weryfikacja materiału w pliku CSV
            materiały_dict = load_materials_dict()
            if material_kod in materiały_dict:
                material_nazwa_wyswietlana = materiały_dict[material_kod]
                
                opis_clean = remove_polish_chars(opis)
                material_kod_clean = remove_polish_chars(material_kod)

                # Schemat: ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu
                wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb_{kod_produktu}"
            else:
                error_message = "Nie znaleziono takiego materiału"

    return render_template(
        'index.html',
        nazwa=wygenerowana_nazwa,
        error=error_message,
        material_nazwa=material_nazwa_wyswietlana,
        form=form_data
    )

@app.route('/pomoc')
def pomoc():
    return render_template('help.html')

if __name__ == '__main__':
    app.run(debug=True)