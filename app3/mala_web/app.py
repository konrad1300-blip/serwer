from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Dodaj to po utworzeniu 'app'
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Stałe na stałe wpisane do programu
STALA_MALARSKA = 1.333        # ml/m²
STALA_SPRZATANIA = 100        # ml

@app.route('/')
def index():
    # Domyślne wartości przy pierwszym wejściu
    dane = {
        'metry': 1,
        'kolory': 1,
        'ilosc_sztuk': 1,
        'metoda': 'sit',
        'podloze': 'PVC'
    }
    return render_template('index.html', dane=dane)

@app.route('/oblicz', methods=['POST'])
def oblicz():
    try:
        # Pobranie danych z formularza
        metry = float(request.form['metry'])
        kolory = int(request.form['kolory'])
        ilosc_sztuk = int(request.form['ilosc_sztuk'])
        metoda = request.form['metoda']
        podloze = request.form['podloze']

        # Zachowanie danych do ponownego wyświetlenia w formularzu
        dane = {
            'metry': metry,
            'kolory': kolory,
            'ilosc_sztuk': ilosc_sztuk,
            'metoda': metoda,
            'podloze': podloze
        }

        # Obliczenie ilości farby bazowej wg wzoru
        if metoda == 'sit':
            farba_ml = (metry * STALA_MALARSKA + (STALA_SPRZATANIA / ilosc_sztuk)) * kolory
        else:  # szablon (mnożnik 3.5)
            farba_ml = (metry * STALA_MALARSKA * 3.5 + (STALA_SPRZATANIA / ilosc_sztuk)) * kolory

        # Przeliczenie na litry
        farba_l = round(farba_ml / 1000.0, 4)

        # Obliczenie rozpuszczalników w zależności od podłoża
        if podloze == 'PVC':
            rozcienczalnik_l = round(farba_l * 0.15, 4)
            opozniacz_l = round(farba_l * 0.05, 4)
            calkowita_l = round(farba_l + rozcienczalnik_l + opozniacz_l, 4)
            wynik = {
                'farba': farba_l,
                'rozcienczalnik_plv': rozcienczalnik_l,
                'opozniacz_sv1': opozniacz_l,
                'calkowita': calkowita_l,
                'podloze': 'PVC',
                'komunikat': ''
            }
        else:  # FRETARP
            rozcienczalnik_l = round(farba_l * 0.5, 4)
            calkowita_l = round(farba_l + rozcienczalnik_l, 4)
            wynik = {
                'farba': farba_l,
                'rozcienczalnik_qnv': rozcienczalnik_l,
                'calkowita': calkowita_l,
                'podloze': 'FRETARP',
                'komunikat': 'Pamiętaj o odtłuszczeniu powierzchni alkoholem IPA lub zmywaczem 628.'
            }

        return render_template('index.html', wynik=wynik, dane=dane)
    except Exception as e:
        # W przypadku błędu też zachowaj wpisane wartości
        dane = {
            'metry': request.form.get('metry', 1),
            'kolory': request.form.get('kolory', 1),
            'ilosc_sztuk': request.form.get('ilosc_sztuk', 1),
            'metoda': request.form.get('metoda', 'sit'),
            'podloze': request.form.get('podloze', 'PVC')
        }
        return render_template('index.html', error=f"Błąd: {e}", dane=dane)

@app.route('/pomoc')
def pomoc():
    return render_template('pomoc.html')

if __name__ == '__main__':
    app.run(debug=True)