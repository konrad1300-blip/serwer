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


def remove_polish_chars(input_str):
    """Odpowiednik funkcji RemovePolishChars z Pascala.
    Usuwa polskie 'ogonki', chroniąc systemy operacyjne maszyn krojczych przed błędami.
    """
    if not input_str:
        return ""

    mapping = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }

    clean_str = "".join(mapping.get(char, char) for char in input_str)
    return clean_str

app.config['APPLICATION_ROOT'] = '/app9'

@app.route('/', methods=['GET', 'POST'])
def index():
    wygenerowana_nazwa = ""

    # Inicjalizacja słownika pustymi wartościami (zapobiega czyszczeniu formularza po wysłaniu)
    form_data = {
        'ilosc_szt': '', 'opis': '', 'material': 'pvc', 'wydajnosc': '', 'dlugosc': '',
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        # 1. Pobieranie danych tekstowych wprowadzonych przez użytkownika
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material = request.form.get('material', '').strip()
        wydajnosc = request.form.get('wydajnosc', '').strip()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        # 2. Pobieranie opcji Radio / Select
        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        # Zachowanie wprowadzonych wartości, aby użytkownik nie musiał wpisywać ich od nowa
        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material': material,
            'wydajnosc': wydajnosc, 'dlugosc': dlugosc, 'strona': strona,
            'kolor_pisaka': kolor_pisaka, 'maszyna': maszyna,
            'kod_produktu': kod_produktu
        }

        # 3. Filtrowanie polskich znaków w polach tekstowych podatnych na błędy maszynowe
        opis = remove_polish_chars(opis)
        material = remove_polish_chars(material)

        # 4. Konstrukcja nazwy pliku według schematu z kodu Pascal,
        # z dodanym na końcu kodem produktu po znaku '_':
        # ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material + "_" + opis + "_Wyd" + wydajnosc + "%_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu
        wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material}_{opis}_Wyd{wydajnosc}%_{maszyna}_{dlugosc}mb"
        if kod_produktu:
            wygenerowana_nazwa += f"_{kod_produktu}"

    return render_template('index.html', nazwa=wygenerowana_nazwa, form=form_data)


@app.route('/pomoc')
def pomoc():
    return render_template('help.html')


if __name__ == '__main__':
    app.run(debug=True)
