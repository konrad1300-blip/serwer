
Gemini
Nowy czat
Szukaj na czatach
Filmy
Biblioteka
Nowy notatnik
modyfikacja aplikacji
Architektura Systemu Wycen i Planowania Produkcji SWTP
Wszystkie notatniki
Aktualizacja Generatora Nazw Plików Kroju
Modyfikacja generatora nazw plików
Automatyzacja Nazewnictwa Procesów Produkcyjnych
Zarządzanie użytkownikami i hasłami w aplikacji
O książce "Gödel, Escher, Bach"
Analiza Projektu freeKasia RAG
Rozwinięcie skrótu GNPK
Dodawanie logowania użytkownika do aplikacji
Instalacja Antigravity IDE na Ubuntu
Jak połączyć GitHub z Lovable
Tworzenie aplikacji dla nauczycielki polskiego
Dodanie kolumny do zapytania SQL
Rekomendowane restauracje w Pile i okolicy
Systemy RAG: Od podstaw do zaawansowania
Python z Pandas zamiast SQL
Konfiguracja lokalnych modeli LLM w Goose
Claude Cowork Dostępność w Planach
Wakacyjna Wycieczka W Okolicach Sandomierza
PowerShell Command Syntax Error
Systemy planowania produkcji: ERP, APS, MES
Wygeneruj grafikę 600 x 450 pikseli . Znak ostrzegawczy "W produkcie nie występuje żadna etykieta"
Naprawa błędów w aplikacji Lotto
Kontrola jakości spawanych połączeń metalowych
Plan Budowy Aplikacji CAD/CAM Plandek
Błąd odczytu pliku
Wspólne tworzenie aplikacji w Pythonie
Analiza i Rozwój Aplikacji KIT-zen
porównaj dla mnie języki python i rust w punktach wady i zalety
Analiza i Usprawnienia Aplikacji KIT - zen
Projekt systemu zarządzania zadaniami KIT-zen
Instalacja zależności z requirements.txt
Instalacja bibliotek z requirements.txt
Zarządzanie zasobami działu KiT
Instalacja pakietów z requirements.txt
Słowa na przywracanie spokoju i ładu
`lsof` do sprawdzenia portu 5000
Instalacja bibliotek z requirements.txt
Planowanie aplikacji KIT przyrostowo
Analiza kodu systemu zarządzania projektami
Sprawdzian z potęgowania dla klasy 7
Rozwój aplikacji KIT: Propozycje funkcjonalności
Zmiana uprawnień plików rekurencyjnie
Rozwój Aplikacji KIT: Funkcje i Usprawnienia
Zmiana nazwy i rozszerzenia plików w konsoli
Instalacja PythonOCC: Pip vs Conda
Jak usunąć repozytorium z GitHub
Lokalny RAG dla danych technicznych
Rozwiązywanie problemów z bazą danych Ubuntu
Naprawa ścieżek w aplikacji Flask
Aktualizacja serwera Ubuntu: Poradnik
Odmowa generowania niestosownych obrazów
Komputery Kwantowe: Rewolucja Obliczeniowa
Gunicorn: Konfiguracja i Działanie
Naprawa błędów krytycznych VirtualBox
O czym AI wie o Tobie
Wstawianie i stylizacja linii w HTML
Naprawa przycisku nawigacyjnego w HTML/CSS
Analiza błędów programu "Zgrzewanie 4.0"
Analiza błędów aplikacji Piorun 5.1
Analiza błędów aplikacji Piorun 5.1
Analiza błędów aplikacji Piorun 5.1
Konfiguracja serwera i aplikacji Flask
Vault na Ubuntu: Zarządzanie Sekretami
Wklejanie tekstu w nano
Wygeneruj ikonę dla programu generującego dokumenty "PIORUN"
Python-docx: Tworzenie Dokumentów Word
Darmowy hosting stron internetowych: opcje
Dlaczego Docker Desktop musi być uruchomiony
Docker Compose: Frontend, Backend, Baza Danych
Rysowanie kostki 2m w CAD
Zmiana języka rozmowy na polski
Rozwiązywanie problemów z dostępem sieciowym
Kopiowanie plików w konsoli Linux
na podstawie tych zdjęć wykonaj kolorowy szkic takiej torby w dwóch rzutach.

Aktywność
Piła, Polska
Na podstawie Twoich miejsc (praca)
Zaktualizuj lokalizację
Rozmowa z Gemini
W tej aplikacji chcę zrezygnować z opcji Obie (O) jeśli chodzi o orientacje. Maszyna CNC chcę mieć opcję Zund lub Lectra. konieczne uzupełnienie wszystkich pól z wyjątkiem opis elementu - żeby nie przeszło dalej. Opis elementów max 10 znaków.

Oto zaktualizowany kod aplikacji (wersja v0.5), uwzględniający wprowadzone zmiany:

Usunięto opcję Obie (O) z sekcji Strona / Orientacja.

Zredukowano wybór maszyn CNC wyłącznie do Zund (Zu) i Lectra (Lc).

Wymuszono brak możliwości przejścia dalej bez uzupełnienia wszystkich pól (dodano atrybuty required w HTML oraz walidację w Pythonie) – z wyjątkiem pola Opis elementu, które pozostało opcjonalne.

Nałożono ograniczenie długości pola Opis elementu do maksymalnie 10 znaków (maxlength="10" oraz przycinanie po stronie backendu).

1. app.py
Python
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
        opis = request.form.get('opis', '').strip()[:10]  # Ograniczenie do max 10 znaków
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
2. templates/index.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.5 - Generator Nazw Plików Kroju</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <style>
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .result-box {
            background-color: #e9ecef;
            border: 2px solid #2c3e50;
            border-radius: 10px;
            padding: 15px;
            font-size: 1.1rem;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 25px;
            word-break: break-all;
        }
        .error-box {
            background-color: #f8d7da;
            border: 2px solid #f5c6cb;
            color: #721c24;
            border-radius: 10px;
            padding: 15px;
            font-size: 1.1rem;
            font-weight: bold;
            text-align: center;
            margin-bottom: 25px;
        }
        .material-info {
            font-size: 0.85rem;
            color: #27ae60;
            margin-top: 4px;
            font-weight: bold;
        }
        .form-group-row {
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
        }
        .form-group-row div {
            flex: 1;
        }
        .radio-group {
            display: flex;
            gap: 10px;
            margin-top: 5px;
        }
        button[type="submit"],
        .copy-btn,
        .nav-btn {
            background-color: #2c3e50;
            color: white;
            border: none;
            border-radius: 50px;
            padding: 12px 20px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
            text-align: center;
            text-decoration: none;
            display: inline-block;
        }
        button[type="submit"]:hover,
        .copy-btn:hover,
        .nav-btn:hover {
            background-color: #1a252f;
        }
        .nav-btn {
            width: 100%;
            display: block;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="{{ url_for('index') }}" class="nav-btn">Strona główna</a>

        <div class="top-bar">
            <h1>GNPK v0.5 Web - Generator Nazw Plików Kroju</h1>
            <a href="{{ url_for('pomoc') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">🛈 Instrukcja</a>
        </div>

        {% if error %}
        <div class="error-box">
            {{ error }}
        </div>
        {% endif %}

        {% if nazwa %}
        <div class="result-box" id="result-box">
            <span style="font-size: 0.85rem; color: #7f8c8d; display: block; font-weight: normal; margin-bottom: 5px;">Wygenerowana nazwa pliku:</span>
            <span id="nazwa-pliku">{{ nazwa }}</span>
        </div>
        <div style="text-align: center; margin-bottom: 20px;">
            <button type="button" class="copy-btn" onclick="copyName()">Kopiuj nazwę</button>
        </div>
        {% endif %}

        <form method="POST" action="{{ url_for('index') }}">

            <div class="form-group-row">
                <div>
                    <label for="ilosc_szt">Ilość sztuk:</label>
                    <input type="text" id="ilosc_szt" name="ilosc_szt" value="{{ form.ilosc_szt }}" required placeholder="np. 50">
                </div>
                <div>
                    <label for="material_kod">Materiał (Kod):</label>
                    <input type="text" id="material_kod" name="material_kod" value="{{ form.material_kod }}" required placeholder="M0101-001" maxlength="9" oninput="maskMaterialKod(this)">
                    {% if material_nazwa %}
                    <div class="material-info">✓ Rozpoznano: {{ material_nazwa }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Strona / Orientacja:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %} required> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' or not form.strona %}checked{% endif %} required> Prawa (P)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' or not form.kolor_pisaka %}checked{% endif %} required> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %} required> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %} required> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %} required> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu (opcjonalnie, max 10 zn.):</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod" maxlength="10">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" required placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" required style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' or not form.maszyna %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" required placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
                </div>
            </div>

            <div style="margin-top: 20px; text-align: center;">
                <button type="submit">Zatwierdź i generuj nazwę</button>
            </div>
        </form>
    </div>

    <script>
        function copyName() {
            var textElement = document.getElementById('nazwa-pliku');
            if (!textElement) {
                alert('Nie znaleziono nazwy do skopiowania!');
                return;
            }
            var text = textElement.textContent;

            function showCopiedFeedback() {
                var btn = document.querySelector('.copy-btn');
                if (btn) {
                    var original = btn.textContent;
                    btn.textContent = 'Skopiowano!';
                    setTimeout(function() { btn.textContent = original; }, 1500);
                }
            }

            function fallbackCopy(text) {
                var textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                textarea.style.left = '-9999px';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    var successful = document.execCommand('copy');
                    if (successful) {
                        showCopiedFeedback();
                    } else {
                        alert('Kopiowanie nie powiodło się. Skopiuj ręcznie.');
                    }
                } catch (err) {
                    alert('Kopiowanie nie powiodło się. Skopiuj ręcznie.');
                }
                document.body.removeChild(textarea);
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text)
                    .then(function() {
                        showCopiedFeedback();
                    })
                    .catch(function() {
                        fallbackCopy(text);
                    });
            } else {
                fallbackCopy(text);
            }
        }

        function maskMaterialKod(el) {
            var val = el.value.toUpperCase();
            if (/^[0-9]/.test(val)) {
                val = 'M' + val;
            }
            var raw = val.replace(/[^M0-9]/g, '');
            if (raw.startsWith('M')) {
                var digits = raw.slice(1).replace(/[^0-9]/g, '').slice(0, 7);
                var formatted = 'M';
                if (digits.length > 0) formatted += digits.slice(0, 4);
                if (digits.length > 4) formatted += '-' + digits.slice(4, 7);
                el.value = formatted;
            } else {
                el.value = raw.slice(0, 9);
            }
        }

        function maskKodProduktu(el) {
            var raw = el.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
            var parts = [];
            if (raw.length > 0) parts.push(raw.slice(0, 3));
            if (raw.length > 3) parts.push(raw.slice(3, 7));
            if (raw.length > 7) parts.push(raw.slice(7, 11));
            el.value = parts.join('-');
        }
    </script>
</body>
</html>
3. templates/help.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.5 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.5 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <p><em>Uwaga: Wszystkie pola oprócz "Opis elementu" są wymagane.</em></p>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> w masce <code>Mxxxx-xxx</code> (wymagane).</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie) (wymagane).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony) (wymagane).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis (maksymalnie 10 znaków); polskie znaki są usuwane.</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących (wymagane).</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Lc (Lectra) (wymagane).</li>
            <li><strong>Kod produktu</strong> — kod w masce <code>xxx-xxxx-xxx</code> (wymagane).</li>
        </ul>
    </div>
</body>
</html>
nie zrozumieliśmy się Maszyny CNC pozostają tak jak były plus dodatkowa opcja Zund lub Lectra.

Rozumiem, dziękuję za sprostowanie! Przywróciłem poprzednią listę maszyn CNC (Zund, Lectra, Gerber, Bullmer) oraz dodałem nową, łączoną opcję Zund lub Lectra (ZuLc).

(Użyto skrótu ZuLc, aby uniknąć niedozwolonych znaków takich jak / w nazwach plików).

Poniżej znajduje się kompletny, zaktualizowany kod:

1. app.py
Python
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
2. templates/index.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.5 - Generator Nazw Plików Kroju</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <style>
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .result-box {
            background-color: #e9ecef;
            border: 2px solid #2c3e50;
            border-radius: 10px;
            padding: 15px;
            font-size: 1.1rem;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 25px;
            word-break: break-all;
        }
        .error-box {
            background-color: #f8d7da;
            border: 2px solid #f5c6cb;
            color: #721c24;
            border-radius: 10px;
            padding: 15px;
            font-size: 1.1rem;
            font-weight: bold;
            text-align: center;
            margin-bottom: 25px;
        }
        .material-info {
            font-size: 0.85rem;
            color: #27ae60;
            margin-top: 4px;
            font-weight: bold;
        }
        .form-group-row {
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
        }
        .form-group-row div {
            flex: 1;
        }
        .radio-group {
            display: flex;
            gap: 10px;
            margin-top: 5px;
        }
        button[type="submit"],
        .copy-btn,
        .nav-btn {
            background-color: #2c3e50;
            color: white;
            border: none;
            border-radius: 50px;
            padding: 12px 20px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
            text-align: center;
            text-decoration: none;
            display: inline-block;
        }
        button[type="submit"]:hover,
        .copy-btn:hover,
        .nav-btn:hover {
            background-color: #1a252f;
        }
        .nav-btn {
            width: 100%;
            display: block;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="{{ url_for('index') }}" class="nav-btn">Strona główna</a>

        <div class="top-bar">
            <h1>GNPK v0.5 Web - Generator Nazw Plików Kroju</h1>
            <a href="{{ url_for('pomoc') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">🛈 Instrukcja</a>
        </div>

        {% if error %}
        <div class="error-box">
            {{ error }}
        </div>
        {% endif %}

        {% if nazwa %}
        <div class="result-box" id="result-box">
            <span style="font-size: 0.85rem; color: #7f8c8d; display: block; font-weight: normal; margin-bottom: 5px;">Wygenerowana nazwa pliku:</span>
            <span id="nazwa-pliku">{{ nazwa }}</span>
        </div>
        <div style="text-align: center; margin-bottom: 20px;">
            <button type="button" class="copy-btn" onclick="copyName()">Kopiuj nazwę</button>
        </div>
        {% endif %}

        <form method="POST" action="{{ url_for('index') }}">

            <div class="form-group-row">
                <div>
                    <label for="ilosc_szt">Ilość sztuk:</label>
                    <input type="text" id="ilosc_szt" name="ilosc_szt" value="{{ form.ilosc_szt }}" required placeholder="np. 50">
                </div>
                <div>
                    <label for="material_kod">Materiał (Kod):</label>
                    <input type="text" id="material_kod" name="material_kod" value="{{ form.material_kod }}" required placeholder="M0101-001" maxlength="9" oninput="maskMaterialKod(this)">
                    {% if material_nazwa %}
                    <div class="material-info">✓ Rozpoznano: {{ material_nazwa }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Strona / Orientacja:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %} required> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' or not form.strona %}checked{% endif %} required> Prawa (P)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' or not form.kolor_pisaka %}checked{% endif %} required> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %} required> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %} required> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %} required> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu (opcjonalnie, max 10 zn.):</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod" maxlength="10">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" required placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" required style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' or not form.maszyna %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Ge" {% if form.maszyna == 'Ge' %}selected{% endif %}>Gerber (Ge)</option>
                        <option value="Bu" {% if form.maszyna == 'Bu' %}selected{% endif %}>Bullmer (Bu)</option>
                        <option value="ZuLc" {% if form.maszyna == 'ZuLc' %}selected{% endif %}>Zund lub Lectra (ZuLc)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" required placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
                </div>
            </div>

            <div style="margin-top: 20px; text-align: center;">
                <button type="submit">Zatwierdź i generuj nazwę</button>
            </div>
        </form>
    </div>

    <script>
        function copyName() {
            var textElement = document.getElementById('nazwa-pliku');
            if (!textElement) {
                alert('Nie znaleziono nazwy do skopiowania!');
                return;
            }
            var text = textElement.textContent;

            function showCopiedFeedback() {
                var btn = document.querySelector('.copy-btn');
                if (btn) {
                    var original = btn.textContent;
                    btn.textContent = 'Skopiowano!';
                    setTimeout(function() { btn.textContent = original; }, 1500);
                }
            }

            function fallbackCopy(text) {
                var textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                textarea.style.left = '-9999px';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    var successful = document.execCommand('copy');
                    if (successful) {
                        showCopiedFeedback();
                    } else {
                        alert('Kopiowanie nie powiodło się. Skopiuj ręcznie.');
                    }
                } catch (err) {
                    alert('Kopiowanie nie powiodło się. Skopiuj ręcznie.');
                }
                document.body.removeChild(textarea);
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text)
                    .then(function() {
                        showCopiedFeedback();
                    })
                    .catch(function() {
                        fallbackCopy(text);
                    });
            } else {
                fallbackCopy(text);
            }
        }

        function maskMaterialKod(el) {
            var val = el.value.toUpperCase();
            if (/^[0-9]/.test(val)) {
                val = 'M' + val;
            }
            var raw = val.replace(/[^M0-9]/g, '');
            if (raw.startsWith('M')) {
                var digits = raw.slice(1).replace(/[^0-9]/g, '').slice(0, 7);
                var formatted = 'M';
                if (digits.length > 0) formatted += digits.slice(0, 4);
                if (digits.length > 4) formatted += '-' + digits.slice(4, 7);
                el.value = formatted;
            } else {
                el.value = raw.slice(0, 9);
            }
        }

        function maskKodProduktu(el) {
            var raw = el.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
            var parts = [];
            if (raw.length > 0) parts.push(raw.slice(0, 3));
            if (raw.length > 3) parts.push(raw.slice(3, 7));
            if (raw.length > 7) parts.push(raw.slice(7, 11));
            el.value = parts.join('-');
        }
    </script>
</body>
</html>
3. templates/help.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.5 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.5 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <p><em>Uwaga: Wszystkie pola oprócz "Opis elementu" są wymagane.</em></p>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> w masce <code>Mxxxx-xxx</code> (wymagane).</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie) (wymagane).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony) (wymagane).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis (maksymalnie 10 znaków); polskie znaki są usuwane.</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących (wymagane).</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Lc (Lectra), Ge (Gerber), Bu (Bullmer), ZuLc (Zund lub Lectra) (wymagane).</li>
            <li><strong>Kod produktu</strong> — kod w masce <code>xxx-xxxx-xxx</code> (wymagane).</li>
        </ul>
    </div>
</body>
</html>
uaktualnij jeszcze pliki requirements.txt i plan.md i wygeneruj ich kompletny kod

Opis Składników Nazwy:
Pole	Typ / Wymaganość	Opis i Dopuszczalne Wartości	Przykład
Ilość sztuk	Wymagane	Liczba sztuk w układzie	50 -> 50szt
Strona / Orientacja	Wymagane	L (Lewa), P (Prawa)	P
Kolor pisaka	Wymagane	Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony)	Cz
Kod materiału	Wymagane	Format maski Mxxxx-xxx (np. M0101-001), weryfikowane w materiały.csv	M0101-001
Opis elementu	Opcjonalne	Dodatkowy opis, max 10 znaków, automatyczne czyszczenie polskich znaków	Przod
Maszyna CNC	Wymagane	Zu (Zund), Lc (Lectra), Ge (Gerber), Bu (Bullmer), ZuLc (Zund lub Lectra)	Zu
Długość układu	Wymagane	Długość układu w metrach bieżących	4.5 -> 4.5mb
Kod produktu	Wymagane	Format maski xxx-xxxx-xxx	001-0001-001
3. Kluczowe Funkcjonalności i Walidacja
Pola Wymagane vs Opcjonalne:

Wszelkie pola poza opisanym jako Opis elementu są bezwzględnie wymagane do wygenerowania nazwy pliku.

Pole Opis elementu pozostaje opcjonalne (max 10 znaków).

Ograniczenia znaków i sanitizacja:

Automatyczne usuwanie polskich ogonków (ą -> a, ł -> l, itp.) dla zabezpieczenia odczytu w systemach operacyjnych maszyn CNC.

Wymuszenie wielkich liter dla kodów materiałowych oraz kodów produktów.

Masekowanie i Walidacja JavaScript (Frontend):

Wpisanie cyfry w kodzie materiału automatycznie dodaje prefiks M oraz tworzy łącznik Mxxxx-xxx.

Kod produktu automatycznie rozdzielany jest myślnikami xxx-xxxx-xxx.

Weryfikacja bazy materiałów (CSV):

Odczyt z pliku materiały.csv z automatyczną detekcją separatora (przecinek , lub średnik ;).

W przypadku braku kodu w bazie, wyświetlany jest czytelny komunikat błędu.

Kopiowanie do schowka:

Dedykowany przycisk JavaScript z obsługa wywołań w trybach zabezpieczonych (HTTPS API) oraz z automatycznym fallbackiem.

Wsparcie dla Reverse Proxy (WSGI Middleware):

Konfiguracja ProxyFix zapewniająca poprawną współpracę przy serwowaniu aplikacji pod podścieżką (np. /app9).

4. Struktura Katalogów i Plików
Plaintext
/
├── app.py                  # Główny kod backendowy aplikacji (Flask)
├── materiały.csv           # Baza materiałów (Kod;Nazwa)
├── requirements.txt        # Lista zależności Python
├── plan.md                 # Pełna dokumentacja i plan rozwoju
├── static/
│   └── style.css           # Style CSS aplikacji
└── templates/
    ├── index.html          # Główny formularz i prezentacja wyników
    └── help.html           # Strona instrukcji użytkownika
5. Wymagania Techniczne i Zależności (requirements.txt)
Python: 3.10+

Biblioteki:

Flask>=3.0.0

Werkzeug>=3.0.0

gunicorn>=21.2.0 (dla środowiska produkcyjnego)

6. Historia Zmian (Changelog)
v0.5 (Obecna wersja)
Strona / Orientacja: Usunięto opcję Obie (O). Pozostawiono wyłącznie Lewa (L) i Prawa (P).

Maszyny CNC: Przywrócono pełną listę maszyn (Zund, Lectra, Gerber, Bullmer) oraz dodano połączoną opcję Zund lub Lectra (ZuLc).

Opis elementu: Ograniczono długość do maksymalnie 10 znaków.

Walidacja: Wprowadzono bezwzględną walidację pól wymaganych po stronie frontendu (required) oraz backendu Python.

Słownik materiałów: Poprawiono wyciąganie i dopasowanie kodów materiałów.

7. Dalsze Plany Rozwoju (Roadmap)
[ ] Implementacja eksportu wygenerowanych nazw do pliku dziennika (log / CSV).

[ ] Możliwość masowego generowania nazw z pliku zbiorczego (Excel / CSV).

[ ] Panel administracyjny do dodawania i edycji materiałów bezpośrednio w przeglądarce.
"""

with open('plan.md', 'w', encoding='utf-8') as f:
f.write(plan_content)

print("FILES_CREATED_SUCCESSFULLY")


```text?code_stdout&code_event_index=1
FILES_CREATED_SUCCESSFULLY

Oto zaktualizowane pliki requirements.txt oraz plan.md dostosowane do najnowszej wersji aplikacji GNPK v0.5 Web.

Pliki zostały wygenerowane:

requirements.txt: 
Ikona TXT
requirements
 TXT 
Otwórz

plan.md: 
Ikona MD
plan
 MD 
Otwórz

1. requirements.txt
Plaintext
Flask>=3.0.0
Werkzeug>=3.0.0
gunicorn>=21.2.0
2. plan.md
Markdown
# GNPK v0.5 Web - Generator Nazw Plików Kroju
## Dokumentacja Techniczna i Plan Projektu

---

### 1. Przegląd Projektu (Overview)
Aplikacja **GNPK v0.5 Web** służy do automatycznego i standaryzowanego generowania nazw plików wyjściowych przeznaczonych dla maszyn krojczych CNC (krojownia). Narzędzie zapewnia poprawność formatowania, usuwa polskie znaki diakrytyczne (zapobiegając błędom w oprogramowaniu maszyn) oraz weryfikuje kody materiałowe z bazą danych CSV.

---

### 2. Schemat Generowanej Nazwy Pliku
Wygenerowana nazwa pliku budowana jest według następującego wzorca:

```text
{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod}_{opis}_{maszyna}_{dlugosc}mb_{kod_produktu}
Opis Składników Nazwy:
Pole	Typ / Wymaganość	Opis i Dopuszczalne Wartości	Przykład
Ilość sztuk	Wymagane	Liczba sztuk w układzie	50 -> 50szt
Strona / Orientacja	Wymagane	L (Lewa), P (Prawa)	P
Kolor pisaka	Wymagane	Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony)	Cz
Kod materiału	Wymagane	Format maski Mxxxx-xxx (np. M0101-001), weryfikowane w materiały.csv	M0101-001
Opis elementu	Opcjonalne	Dodatkowy opis, max 10 znaków, automatyczne czyszczenie polskich znaków	Przod
Maszyna CNC	Wymagane	Zu (Zund), Lc (Lectra), Ge (Gerber), Bu (Bullmer), ZuLc (Zund lub Lectra)	Zu
Długość układu	Wymagane	Długość układu w metrach bieżących	4.5 -> 4.5mb
Kod produktu	Wymagane	Format maski xxx-xxxx-xxx	001-0001-001
3. Kluczowe Funkcjonalności i Walidacja
Pola Wymagane vs Opcjonalne:

Wszelkie pola poza opisanym jako Opis elementu są bezwzględnie wymagane do wygenerowania nazwy pliku.

Pole Opis elementu pozostaje opcjonalne (max 10 znaków).

Ograniczenia znaków i sanitizacja:

Automatyczne usuwanie polskich ogonków (ą -> a, ł -> l, itp.) dla zabezpieczenia odczytu w systemach operacyjnych maszyn CNC.

Wymuszenie wielkich liter dla kodów materiałowych oraz kodów produktów.

Masekowanie i Walidacja JavaScript (Frontend):

Wpisanie cyfry w kodzie materiału automatycznie dodaje prefiks M oraz tworzy łącznik Mxxxx-xxx.

Kod produktu automatycznie rozdzielany jest myślnikami xxx-xxxx-xxx.

Weryfikacja bazy materiałów (CSV):

Odczyt z pliku materiały.csv z automatyczną detekcją separatora (przecinek , lub średnik ;).

W przypadku braku kodu w bazie, wyświetlany jest czytelny komunikat błędu.

Kopiowanie do schowka:

Dedykowany przycisk JavaScript z obsługą wywołań w trybach zabezpieczonych (HTTPS API) oraz z automatycznym fallbackiem.

Wsparcie dla Reverse Proxy (WSGI Middleware):

Konfiguracja ProxyFix zapewniająca poprawną współpracę przy serwowaniu aplikacji pod podścieżką (np. /app9).

4. Struktura Katalogów i Plików
Plaintext
/
├── app.py                  # Główny kod backendowy aplikacji (Flask)
├── materiały.csv           # Baza materiałów (Kod;Nazwa)
├── requirements.txt        # Lista zależności Python
├── plan.md                 # Pełna dokumentacja i plan rozwoju
├── static/
│   └── style.css           # Style CSS aplikacji
└── templates/
    ├── index.html          # Główny formularz i prezentacja wyników
    └── help.html           # Strona instrukcji użytkownika
5. Wymagania Techniczne i Zależności (requirements.txt)
Python: 3.10+

Biblioteki:

Flask>=3.0.0

Werkzeug>=3.0.0

gunicorn>=21.2.0 (dla środowiska produkcyjnego)

6. Historia Zmian (Changelog)
v0.5 (Obecna wersja)
Strona / Orientacja: Usunięto opcję Obie (O). Pozostawiono wyłącznie Lewa (L) i Prawa (P).

Maszyny CNC: Przywrócono pełną listę maszyn (Zund, Lectra, Gerber, Bullmer) oraz dodano połączoną opcję Zund lub Lectra (ZuLc).

Opis elementu: Ograniczono długość do maksymalnie 10 znaków.

Walidacja: Wprowadzono bezwzględną walidację pól wymaganych po stronie frontendu (required) oraz backendu Python.

Słownik materiałów: Poprawiono wyciąganie i dopasowanie kodów materiałów.

7. Dalsze Plany Rozwoju (Roadmap)
[ ] Implementacja eksportu wygenerowanych nazw do pliku dziennika (log / CSV).

[ ] Możliwość masowego generowania nazw z pliku zbiorczego (Excel / CSV).

[ ] Panel administracyjny do dodawania i edycji materiałów bezpośrednio w przeglądarce.




Gemini to AI i może popełniać błędy, także co do ludzi. Twoja prywatność i GeminiOtwiera się w nowym oknie

# GNPK v0.5 Web - Generator Nazw Plików Kroju
## Dokumentacja Techniczna i Plan Projektu

---

### 1. Przegląd Projektu (Overview)
Aplikacja **GNPK v0.5 Web** służy do automatycznego i standaryzowanego generowania nazw plików wyjściowych przeznaczonych dla maszyn krojczych CNC (krojownia). Narzędzie zapewnia poprawność formatowania, usuwa polskie znaki diakrytyczne (zapobiegając błędom w oprogramowaniu maszyn) oraz weryfikuje kody materiałowe z bazą danych CSV.

---

### 2. Schemat Generowanej Nazwy Pliku
Wygenerowana nazwa pliku budowana jest według następującego wzorca:

```text
{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod}_{opis}_{maszyna}_{dlugosc}mb_{kod_produktu}
```

#### Opis Składników Nazwy:
| Pole | Typ / Wymaganość | Opis i Dopuszczalne Wartości | Przykład |
| :--- | :--- | :--- | :--- |
| **Ilość sztuk** | Wymagane | Liczba sztuk w układzie | `50` -> `50szt` |
| **Strona / Orientacja** | Wymagane | `L` (Lewa), `P` (Prawa) | `P` |
| **Kolor pisaka** | Wymagane | `Cz` (Czarny), `S` (Srebrny), `N` (Niebieski), `Z` (Zielony) | `Cz` |
| **Kod materiału** | Wymagane | Format maski `Mxxxx-xxx` (np. `M0101-001`), weryfikowane w `materiały.csv` | `M0101-001` |
| **Opis elementu** | Opcjonalne | Dodatkowy opis, max **10 znaków**, automatyczne czyszczenie polskich znaków | `Przod` |
| **Maszyna CNC** | Wymagane | `Zu` (Zund), `Lc` (Lectra), `Ge` (Gerber), `Bu` (Bullmer), `ZuLc` (Zund lub Lectra) | `Zu` |
| **Długość układu** | Wymagane | Długość układu w metrach bieżących | `4.5` -> `4.5mb` |
| **Kod produktu** | Wymagane | Format maski `xxx-xxxx-xxx` | `001-0001-001` |

---

### 3. Kluczowe Funkcjonalności i Walidacja
1. **Pola Wymagane vs Opcjonalne:**
   - Wszelkie pola poza opisanym jako *Opis elementu* są bezwzględnie wymagane do wygenerowania nazwy pliku.
   - Pole *Opis elementu* pozostaje opcjonalne (max 10 znaków).
2. **Ograniczenia znaków i sanitizacja:**
   - Automatyczne usuwanie polskich ogonków (`ą` -> `a`, `ł` -> `l`, itp.) dla zabezpieczenia odczytu w systemach operacyjnych maszyn CNC.
   - Wymuszenie wielkich liter dla kodów materiałowych oraz kodów produktów.
3. **Masekowanie i Walidacja JavaScript (Frontend):**
   - Wpisanie cyfry w kodzie materiału automatycznie dodaje prefiks `M` oraz tworzy łącznik `Mxxxx-xxx`.
   - Kod produktu automatycznie rozdzielany jest myślnikami `xxx-xxxx-xxx`.
4. **Weryfikacja bazy materiałów (CSV):**
   - Odczyt z pliku `materiały.csv` z automatyczną detekcją separatora (przecinek `,` lub średnik `;`).
   - W przypadku braku kodu w bazie, wyświetlany jest czytelny komunikat błędu.
5. **Kopiowanie do schowka:**
   - Dedykowany przycisk JavaScript z obsługa wywołań w trybach zabezpieczonych (HTTPS API) oraz z automatycznym fallbackiem.
6. **Wsparcie dla Reverse Proxy (WSGI Middleware):**
   - Konfiguracja `ProxyFix` zapewniająca poprawną współpracę przy serwowaniu aplikacji pod podścieżką (np. `/app9`).

---

### 4. Struktura Katalogów i Plików
```text
/
├── app.py                  # Główny kod backendowy aplikacji (Flask)
├── materiały.csv           # Baza materiałów (Kod;Nazwa)
├── requirements.txt        # Lista zależności Python
├── plan.md                 # Pełna dokumentacja i plan rozwoju
├── static/
│   └── style.css           # Style CSS aplikacji
└── templates/
    ├── index.html          # Główny formularz i prezentacja wyników
    └── help.html           # Strona instrukcji użytkownika
```

---

### 5. Wymagania Techniczne i Zależności (`requirements.txt`)
- **Python:** 3.10+
- **Biblioteki:**
  - `Flask>=3.0.0`
  - `Werkzeug>=3.0.0`
  - `gunicorn>=21.2.0` (dla środowiska produkcyjnego)

---

### 6. Historia Zmian (Changelog)

#### **v0.5 (Obecna wersja)**
- **Strona / Orientacja:** Usunięto opcję *Obie (O)*. Pozostawiono wyłącznie *Lewa (L)* i *Prawa (P)*.
- **Maszyny CNC:** Przywrócono pełną listę maszyn (*Zund*, *Lectra*, *Gerber*, *Bullmer*) oraz dodano połączoną opcję *Zund lub Lectra* (`ZuLc`).
- **Opis elementu:** Ograniczono długość do maksymalnie 10 znaków.
- **Walidacja:** Wprowadzono bezwzględną walidację pól wymaganych po stronie frontendu (`required`) oraz backendu Python.
- **Słownik materiałów:** Poprawiono wyciąganie i dopasowanie kodów materiałów.

---

### 7. Dalsze Plany Rozwoju (Roadmap)
- [ ] Implementacja eksportu wygenerowanych nazw do pliku dziennika (log / CSV).
- [ ] Możliwość masowego generowania nazw z pliku zbiorczego (Excel / CSV).
- [ ] Panel administracyjny do dodawania i edycji materiałów bezpośrednio w przeglądarce.