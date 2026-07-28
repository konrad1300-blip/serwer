from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Dodaj to po utworzeniu 'app'
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Stałe mapowania
THREAD_MULTIPLIER = {
    '10': 1.03,
    '20': 1.0,
    '30': 0.95,
    '40': 0.8
}

MATERIAL_THICKNESS = {
    'PVC 650gr': 0.0004,
    'PVC 900gr': 0.0012,
    'PVC 1400gr': 0.0022,
    'Freetarp': 0.0005
}

LAYERS_CHOICES = [str(i) for i in range(1, 9)]
BOBBIN_CHOICES = ['600', '900', '1000', '1200', '1250', '2500',
                  '3000', '3350', '3500', '4000', '4500', '5000']

MSTEB = 2.61644          # stała dla ściegu stebnówkowego
TECH_LOSS = 1.15         # 15% straty technologicznej

# Grubości pasów
POLYESTER_STRIP = 0.00512
PVC_STRIP = 0.00482

def calculate(data):
    """
    data: dict z formularza
    zwraca krotkę (metry, szpulki) lub None w przypadku błędu
    """
    try:
        stitch_length = float(data.get('stitch_length', '1'))
        stitch_density = float(data.get('stitch_density', '180'))
        thread_choice = data.get('thread', '10')
        material_choice = data.get('material', 'PVC 650gr')
        layers = int(data.get('layers', '1'))
        bobbin_length = int(data.get('bobbin', '600'))

        # Pobranie mnożników
        grnici = THREAD_MULTIPLIER.get(thread_choice, 1.03)
        grmaterialu = MATERIAL_THICKNESS.get(material_choice, 0.0004)

        # Pasy
        papoliester = POLYESTER_STRIP if data.get('pas_poliestrowy') == 'on' else 0
        paPVC = PVC_STRIP if data.get('pas_pvc') == 'on' else 0

        # Grubość materiału do przeszycia
        GM = (layers * grmaterialu * grnici) + papoliester + paPVC

        # Wynik w metrach
        wynik_metry = round(((GM * stitch_density) + (stitch_length * MSTEB)) * TECH_LOSS, 5)

        # Wynik w szpulach
        wynik_szpule = round(wynik_metry / bobbin_length, 4)

        return wynik_metry, wynik_szpule

    except (ValueError, KeyError, TypeError):
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    result_metry = None
    result_szpule = None
    error = None
    form_data = request.form if request.method == 'POST' else {}

    if request.method == 'POST':
        calc_result = calculate(request.form)
        if calc_result:
            result_metry, result_szpule = calc_result
        else:
            error = "Wprowadź poprawne dane liczbowe."

    return render_template('index.html',
                           result_metry=result_metry,
                           result_szpule=result_szpule,
                           error=error,
                           form_data=form_data,
                           thread_choices=THREAD_MULTIPLIER.keys(),
                           material_choices=MATERIAL_THICKNESS.keys(),
                           layers_choices=LAYERS_CHOICES,
                           bobbin_choices=BOBBIN_CHOICES)

@app.route('/pomoc')
def pomoc():
    return render_template('pomoc.html')

if __name__ == '__main__':
    app.run(debug=True)