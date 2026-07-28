
Gemini
Nowy czat
Szukaj na czatach
Filmy
Biblioteka
Nowy notatnik
Architektura Systemu Wycen i Planowania Produkcji SWTP
chciałbym listę rekomentowanych restauracji w Pile woj. wielkopolskie i okolicach w promieniu 70 km
Wszystkie notatniki
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

Aktywność
Piła, Polska
Na podstawie Twoich miejsc (praca)
Zaktualizuj lokalizację
Rozmowa z Gemini
chcę przerobić tą aplikację w taki sposób, że rezygnuje z członu wydajność, a materiały będą wpisywane w polu materiał według kodu pierwszej kolumny pliku cvs. druga koluma pliku cvs ma się wyświetlać w oknie programu (na stronie) ale nie dołaczamy jej do wygenerowanego ciągu nazwy pliku, tam dołaczamy tylko kod M01.... - taki jak został wpisany w pole materiały. jeśli kod jest błedny albo nie ma takiego kodu w pliku cvs to program ma wypisać ,że nie znlazł takiego materiału.

Oto zaktualizowany kod aplikacji Flask, szablonu index.html oraz instrukcji help.html uwzględniający opisaną modyfikację.

Główne zmiany:
Brak członu wydajności – usuwamy pole wydajności z formularza i z logiki generowania ciągu znaków.

Obsługa pliku CSV – aplikacja wczytuje plik materiały.csv (zakładamy separator domyślny , lub ;). Słownik mapuje kody z pierwszej kolumny (np. M01) na opis z drugiej kolumny (np. Tkanina PVC 650g).

Weryfikacja materiału:

Jeśli podany kod istnieje w pliku CSV: w nazwie pliku używamy wyłącznie wpisanego kodu (np. M01), natomiast w widoku na stronie pod polem materiału/w specjalnym komunikacie wyświetlamy opis z drugiej kolumny.

Jeśli kod jest błędny lub nie występuje w pliku CSV: aplikacja wyświetla komunikat „Nie znaleziono takiego materiału” i nie generuje błędnej nazwy pliku.

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
            # Automatyczne wykrywanie separatora (, lub ;)
            sample = f.read(2048)
            f.seek(0)
            delimiter = ';' if ';' in sample else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                if len(row) >= 2:
                    code = row[0].strip()
                    name = row[1].strip()
                    if code:
                        materials[code] = name
    return materials

def remove_polish_chars(input_str):
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
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material_kod = request.form.get('material_kod', '').strip()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Weryfikacja materiału w pliku CSV
        materiały_dict = load_materials_dict()
        if material_kod in materiały_dict:
            material_nazwa_wyswietlana = materiały_dict[material_kod]
            
            opis_clean = remove_polish_chars(opis)
            material_kod_clean = remove_polish_chars(material_kod)

            # Schemat bez członu wydajności:
            # ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb"
            wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb"
            if kod_produktu:
                wygenerowana_nazwa += f"_{kod_produktu}"
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
    <title>GNPK v0.2 - Generator Nazw Plików Kroju</title>
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
            <h1>GNPK v0.2 Web - Generator Nazw Plików Kroju</h1>
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
                    <input type="text" id="material_kod" name="material_kod" value="{{ form.material_kod }}" required placeholder="np. M01">
                    {% if material_nazwa %}
                    <div class="material-info">✓ Rozpoznano: {{ material_nazwa }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Strona / Orientacja:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %}> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' %}checked{% endif %}> Prawa (P)</label>
                        <label><input type="radio" name="strona" value="O" {% if form.strona == 'O' %}checked{% endif %}> Obie (O)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' %}checked{% endif %}> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %}> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %}> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %}> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>Jigwei (Jw)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
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
    <title>GNPK v0.2 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.2 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> (np. <code>M01</code>). W oknie aplikacji wyświetli się nazwa z drugiej kolumny, a do nazwy pliku zostanie dodany wyłącznie kod.</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie), O (Obie).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis; polskie znaki są usuwane.</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Jw (Jigwei), Lc (Lectra), Br (Bez różnicy).</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących.</li>
            <li><strong>Kod produktu</strong> — opcjonalny kod w masce <code>xxx-xxxx-xxx</code>; dodawany na końcu nazwy po znaku „_”.</li>
        </ul>
    </div>
</body>
</html>
możesz jeszcze uaktualinić i plik plan.md

Oto zaktualizowana treść pliku plan.md, uwzględniająca usunięcie członu wydajności, walidację kodów materiałów z pliku CSV oraz pełną dokumentację i kod źródłowy nowej wersji aplikacji.

Markdown
# Dokumentacja Projektu: GNPK Web (Generator Nazw Plików Kroju) - v0.3

Projekt polega na migracji i rozbudowie aplikacji **GNPK** (Generator Nazw Plików Kroju) do nowoczesnej aplikacji webowej uruchamianej na serwerze. Całość opiera się na mikro-frameworku **Flask (Python)** i jest dostosowana do stylistyki wizualnej dostarczonych plików CSS (`style.css`).

---

## 1. Struktura Katalogów Projektu

Aby aplikacja działała poprawnie w środowisku Flask, pliki na serwerze muszą być ułożone w następującej strukturze:

```text
moje_gnpk/
│
├── app.py                     # Główny serwer aplikacji (Python + Flask)
├── materiały.csv              # Baza materiałów (Kolumna 1: Kod, Kolumna 2: Nazwa)
│
├── static/                    # Folder na zasoby statyczne
│   └── style.css              # Stylistyka (zapewniająca spójny wygląd)
│
└── templates/                 # Folder na szablony HTML (system Jinja2)
    ├── index.html             # Główny formularz generatora GNPK
    └── help.html              # Instrukcja / Strona pomocy
2. Główne Założenia i Schemat Generowania Nazw
Schemat generowanego ciągu znaków:
Plaintext
<ilosc>szt_<strona>_<kolor_pisaka>_<kod_materialu>_<opis>_<maszyna>_<dlugosc>mb_<kod_produktu>
Kluczowe funkcjonalności (v0.3):
Rezygnacja z członu wydajności – pole wydajności zostało usunięte z formularza oraz z wynikowej nazwy pliku.

Weryfikacja materiału z pliku CSV (materiały.csv):

Użytkownik wpisuje w pole tekstowe kod materiału (np. M01).

Aplikacja weryfikuje obecność kodu w pierwszej kolumnie pliku materiały.csv.

Jeśli kod istnieje, aplikacja wyświetla opis materiału z drugiej kolumny w oknie programu, ale do nazwy pliku dołącza wyłącznie kod.

Jeśli kod jest nieprawidłowy lub brakuje go w pliku CSV, aplikacja wyświetla komunikat: „Nie znaleziono takiego materiału” i blokuje generowanie nazwy pliku.

Przycisk „Kopiuj nazwę” – umożliwia szybkie skopiowanie wygenerowanego ciągu znaków do schowka systemowego (z obsługą fallback dla HTTP).

Maszyna CNC – wybór spośród opcji: Zund (Zu), Jigwei (Jw), Lectra (Lc), Bez różnicy (Br).

Maskowanie pola „Kod produktu” – obsługa automatycznego formatowania w locie do wzorca XXX-XXXX-XXX.

Przycisk nawigacyjny – pełnej szerokości przycisk „Strona główna” na samej górze interfejsu.

3. Kod Źródłowy Aplikacji
3.1. app.py
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
                    code = row[0].strip()
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
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material_kod = request.form.get('material_kod', '').strip()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Weryfikacja materiału w pliku CSV
        materiały_dict = load_materials_dict()
        if material_kod in materiały_dict:
            material_nazwa_wyswietlana = materiały_dict[material_kod]
            
            opis_clean = remove_polish_chars(opis)
            material_kod_clean = remove_polish_chars(material_kod)

            # Schemat: ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb"
            wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb"
            if kod_produktu:
                wygenerowana_nazwa += f"_{kod_produktu}"
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
3.2. templates/index.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.2 - Generator Nazw Plików Kroju</title>
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
            <h1>GNPK v0.2 Web - Generator Nazw Plików Kroju</h1>
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
                    <input type="text" id="material_kod" name="material_kod" value="{{ form.material_kod }}" required placeholder="np. M01">
                    {% if material_nazwa %}
                    <div class="material-info">✓ Rozpoznano: {{ material_nazwa }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Strona / Orientacja:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %}> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' %}checked{% endif %}> Prawa (P)</label>
                        <label><input type="radio" name="strona" value="O" {% if form.strona == 'O' %}checked{% endif %}> Obie (O)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' %}checked{% endif %}> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %}> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %}> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %}> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>Jigwei (Jw)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
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
3.3. templates/help.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.2 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.2 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> (np. <code>M01</code>). W oknie aplikacji wyświetli się nazwa z drugiej kolumny, a do nazwy pliku zostanie dodany wyłącznie kod.</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie), O (Obie).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis; polskie znaki są usuwane.</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Jw (Jigwei), Lc (Lectra), Br (Bez różnicy).</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących.</li>
            <li><strong>Kod produktu</strong> — opcjonalny kod w masce <code>xxx-xxxx-xxx</code>; dodawany na końcu nazwy po znaku „_”.</li>
        </ul>
    </div>
</body>
</html>
wygeneruj kompletny uaktualniony plik plan.md

2. Główne Założenia i Schemat Generowania Nazw
Schemat generowanego ciągu znaków:
Plaintext
<ilosc>szt_<strona>_<kolor_pisaka>_<kod_materialu>_<opis>_<maszyna>_<dlugosc>mb_<kod_produktu>
Kluczowe funkcjonalności (v0.3):
Rezygnacja z członu wydajności – pole wydajności zostało usunięte z formularza oraz z wynikowej nazwy pliku.

Weryfikacja materiału z pliku CSV (materiały.csv):

Użytkownik wpisuje w pole tekstowe kod materiału (np. M01).

Aplikacja weryfikuje obecność kodu w pierwszej kolumnie pliku materiały.csv.

Jeśli kod istnieje, aplikacja wyświetla opis materiału z drugiej kolumny w oknie programu, ale do nazwy pliku dołącza wyłącznie kod.

Jeśli kod jest nieprawidłowy lub brakuje go w pliku CSV, aplikacja wyświetla komunikat: „Nie znaleziono takiego materiału” i blokuje generowanie nazwy pliku.

Przycisk „Kopiuj nazwę” – umożliwia szybkie skopiowanie wygenerowanego ciągu znaków do schowka systemowego (z obsługą fallback dla HTTP).

Maszyna CNC – wybór spośród opcji: Zund (Zu), Jigwei (Jw), Lectra (Lc), Bez różnicy (Br).

Maskowanie pola „Kod produktu” – obsługa automatycznego formatowania w locie do wzorca XXX-XXXX-XXX.

Przycisk nawigacyjny – pełnej szerokości przycisk „Strona główna” na samej górze interfejsu.

3. Kod Źródłowy Aplikacji
3.1. app.py
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
    \"\"\"Wczytuje plik materiały.csv do słownika: {kod_materialu: nazwa_materialu}.\"\"\"
    materials = {}
    if os.path.exists(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = ';' if ';' in sample else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                if len(row) >= 2:
                    code = row[0].strip()
                    name = row[1].strip()
                    if code:
                        materials[code] = name
    return materials

def remove_polish_chars(input_str):
    \"\"\"Usuwa polskie 'ogonki', chroniąc systemy operacyjne maszyn krojczych przed błędami.\"\"\"
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
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material_kod = request.form.get('material_kod', '').strip()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Weryfikacja materiału w pliku CSV
        materiały_dict = load_materials_dict()
        if material_kod in materiały_dict:
            material_nazwa_wyswietlana = materiały_dict[material_kod]
            
            opis_clean = remove_polish_chars(opis)
            material_kod_clean = remove_polish_chars(material_kod)

            # Schemat: ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb"
            wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb"
            if kod_produktu:
                wygenerowana_nazwa += f"_{kod_produktu}"
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
3.2. templates/index.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.2 - Generator Nazw Plików Kroju</title>
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
            <h1>GNPK v0.2 Web - Generator Nazw Plików Kroju</h1>
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
                    <input type="text" id="material_kod" name="material_kod" value="{{ form.material_kod }}" required placeholder="np. M01">
                    {% if material_nazwa %}
                    <div class="material-info">✓ Rozpoznano: {{ material_nazwa }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Strona / Orientacja:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %}> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' %}checked{% endif %}> Prawa (P)</label>
                        <label><input type="radio" name="strona" value="O" {% if form.strona == 'O' %}checked{% endif %}> Obie (O)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' %}checked{% endif %}> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %}> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %}> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %}> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>Jigwei (Jw)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
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
3.3. templates/help.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.2 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.2 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> (np. <code>M01</code>). W oknie aplikacji wyświetli się nazwa z drugiej kolumny, a do nazwy pliku zostanie dodany wyłącznie kod.</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie), O (Obie).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis; polskie znaki są usuwane.</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Jw (Jigwei), Lc (Lectra), Br (Bez różnicy).</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących.</li>
            <li><strong>Kod produktu</strong> — opcjonalny kod w masce <code>xxx-xxxx-xxx</code>; dodawany na końcu nazwy po znaku „_”.</li>
        </ul>
    </div>
</body>
</html>
"""

with open("plan.md", "w", encoding="utf-8") as f:
f.write(plan_md_content)

print("Plik plan.md został wygenerowany pomyślnie.")


```text?code_stdout&code_event_index=1
Plik plan.md został wygenerowany pomyślnie.

Plik plan.md został pomyślnie uaktualniony i wygenerowany.

Ikona MD
plan
 MD 
Otwórz
Podsumowanie zmian w pliku plan.md:
Nowa specyfikacja (v0.3): Uwzględniono usunięcie pola i członu wydajności z wygenerowanej nazwy pliku.

Weryfikacja z materiały.csv: Zaktualizowano schemat wczytywania i walidacji materiałów (kod z 1. kolumny trafia do nazwy pliku, a nazwa z 2. kolumny wyświetla się w widoku aplikacji). Dodano obsługę komunikatu „Nie znaleziono takiego materiału”.

Pełny kod źródłowy: Zamieszczono kompletne, zaktualizowane wersje plików app.py, templates/index.html oraz templates/help.html.

jeszcze jedno chcę by w polu materiał(Kod) wszystkie litery mamieniane były na wielkie a jeszcze lepiej by weryfikowały się po masce (Mxxxx-xxx) na przykład M0101-001

2. Główne Założenia i Schemat Generowania Nazw
Schemat generowanego ciągu znaków:
Plaintext
<ilosc>szt_<strona>_<kolor_pisaka>_<kod_materialu>_<opis>_<maszyna>_<dlugosc>mb_<kod_produktu>
Kluczowe funkcjonalności (v0.4):
Rezygnacja z członu wydajności – pole wydajności zostało usunięte z formularza oraz z wynikowej nazwy pliku.

Weryfikacja i formatowanie pola Materiał (Kod):

Wszystkie litery wprowadzane w pole kodu materiału są automatycznie konwertowane na wielkie.

Nałożono maskowanie w locie do wzorca Mxxxx-xxx (np. M0101-001).

Aplikacja weryfikuje obecność sformatowanego kodu w pierwszej kolumnie pliku materiały.csv.

Jeśli kod istnieje, aplikacja wyświetla opis materiału z drugiej kolumny w oknie programu, ale do nazwy pliku dołącza wyłącznie kod.

Jeśli kod jest nieprawidłowy lub brakuje go w pliku CSV, aplikacja wyświetla komunikat: „Nie znaleziono takiego materiału” i blokuje generowanie nazwy pliku.

Przycisk „Kopiuj nazwę” – umożliwia szybkie skopiowanie wygenerowanego ciągu znaków do schowka systemowego (z obsługą fallback dla HTTP).

Maszyna CNC – wybór spośród opcji: Zund (Zu), Jigwei (Jw), Lectra (Lc), Bez różnicy (Br).

Maskowanie pola „Kod produktu” – obsługa automatycznego formatowania w locie do wzorca XXX-XXXX-XXX.

Przycisk nawigacyjny – pełnej szerokości przycisk „Strona główna” na samej górze interfejsu.

3. Kod Źródłowy Aplikacji
3.1. app.py
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
    \"\"\"Wczytuje plik materiały.csv do słownika: {kod_materialu: nazwa_materialu}.\"\"\"
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
    \"\"\"Usuwa polskie 'ogonki', chroniąc systemy operacyjne maszyn krojczych przed błędami.\"\"\"
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
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material_kod = request.form.get('material_kod', '').strip().upper()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Weryfikacja materiału w pliku CSV
        materiały_dict = load_materials_dict()
        if material_kod in materiały_dict:
            material_nazwa_wyswietlana = materiały_dict[material_kod]
            
            opis_clean = remove_polish_chars(opis)
            material_kod_clean = remove_polish_chars(material_kod)

            # Schemat: ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb"
            wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb"
            if kod_produktu:
                wygenerowana_nazwa += f"_{kod_produktu}"
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
3.2. templates/index.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.4 - Generator Nazw Plików Kroju</title>
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
            <h1>GNPK v0.4 Web - Generator Nazw Plików Kroju</h1>
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
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %}> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' %}checked{% endif %}> Prawa (P)</label>
                        <label><input type="radio" name="strona" value="O" {% if form.strona == 'O' %}checked{% endif %}> Obie (O)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' %}checked{% endif %}> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %}> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %}> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %}> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>Jigwei (Jw)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
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
            // Jeśli użytkownik wpisze cyfrę na początku, automatycznie dodaj 'M'
            if (/^[0-9]/.test(val)) {
                val = 'M' + val;
            }
            // Zostawiamy 'M' na początku oraz cyfry
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
3.3. templates/help.html
HTML
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.4 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.4 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> formatowany automatycznie do maski <code>Mxxxx-xxx</code> (np. <code>M0101-001</code>). Wszystkie litery są zamieniane na wielkie.</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie), O (Obie).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis; polskie znaki są usuwane.</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Jw (Jigwei), Lc (Lectra), Br (Bez różnicy).</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących.</li>
            <li><strong>Kod produktu</strong> — opcjonalny kod w masce <code>xxx-xxxx-xxx</code>; dodawany na końcu nazwy po znaku „_”.</li>
        </ul>
    </div>
</body>
</html>
"""

with open("plan.md", "w", encoding="utf-8") as f:
f.write(plan_md_content)

print("Plik plan.md został zaktualizowany do v0.4.")


```text?code_stdout&code_event_index=1
Plik plan.md został zaktualizowany do v0.4.

Plik plan.md został zaktualizowany do wersji v0.4.

Ikona MD
plan
 MD 
Otwórz
Co zostało zmienione / dodane:
Automatyczna konwersja na wielkie litery (.upper()):

Po stronie serwera (app.py) oraz klienta (JavaScript) litery są automatycznie sprowadzane do wielkich.

Maskowanie pola „Materiał (Kod)”:

Dodano funkcję JS maskMaterialKod(el), która w locie wymusza wzorzec Mxxxx-xxx (np. M0101-001).

Jeśli wpisana zostanie sama cyfra na początku, skrypt automatycznie dodaje przed nią literę M.

Nałożono ograniczenie długości do 9 znaków (maxlength="9").

Odporność na wielkość liter w materiały.csv:

Słownik materiałów zamienia klucze kody na wielkie litery podczas wczytywania, dzięki czemu wyszukiwanie działa poprawnie niezależnie od tego, jak kody zostały zapisane w pliku CSV.




Gemini to AI i może popełniać błędy, także co do ludzi. Twoja prywatność i GeminiOtwiera się w nowym oknie

# Dokumentacja Projektu: GNPK Web (Generator Nazw Plików Kroju) - v0.4

Projekt polega na migracji i rozbudowie aplikacji **GNPK** (Generator Nazw Plików Kroju) do nowoczesnej aplikacji webowej uruchamianej na serwerze. Całość opiera się na mikro-frameworku **Flask (Python)** i jest dostosowana do stylistyki wizualnej dostarczonych plików CSS (`style.css`).

---

## 1. Struktura Katalogów Projektu

Aby aplikacja działała poprawnie w środowisku Flask, pliki na serwerze muszą być ułożone w następującej strukturze:

```text
moje_gnpk/
│
├── app.py                     # Główny serwer aplikacji (Python + Flask)
├── materiały.csv              # Baza materiałów (Kolumna 1: Kod, Kolumna 2: Nazwa)
│
├── static/                    # Folder na zasoby statyczne
│   └── style.css              # Stylistyka (zapewniająca spójny wygląd)
│
└── templates/                 # Folder na szablony HTML (system Jinja2)
    ├── index.html             # Główny formularz generatora GNPK
    └── help.html              # Instrukcja / Strona pomocy
```

---

## 2. Główne Założenia i Schemat Generowania Nazw

### Schemat generowanego ciągu znaków:
```text
<ilosc>szt_<strona>_<kolor_pisaka>_<kod_materialu>_<opis>_<maszyna>_<dlugosc>mb_<kod_produktu>
```

### Kluczowe funkcjonalności (v0.4):
1. **Rezygnacja z członu wydajności** – pole wydajności zostało usunięte z formularza oraz z wynikowej nazwy pliku.
2. **Weryfikacja i formatowanie pola Materiał (Kod)**:
   - Wszystkie litery wprowadzane w pole kodu materiału są automatycznie konwertowane na wielkie.
   - Nałożono **maskowanie w locie do wzorca `Mxxxx-xxx`** (np. `M0101-001`).
   - Aplikacja weryfikuje obecność sformatowanego kodu w **pierwszej kolumnie** pliku `materiały.csv`.
   - Jeśli kod istnieje, aplikacja wyświetla opis materiału z **drugiej kolumny** w oknie programu, ale do nazwy pliku dołącza wyłącznie kod.
   - Jeśli kod jest nieprawidłowy lub brakuje go w pliku CSV, aplikacja wyświetla komunikat: **„Nie znaleziono takiego materiału”** i blokuje generowanie nazwy pliku.
3. **Przycisk „Kopiuj nazwę”** – umożliwia szybkie skopiowanie wygenerowanego ciągu znaków do schowka systemowego (z obsługą fallback dla HTTP).
4. **Maszyna CNC** – wybór spośród opcji: *Zund (Zu)*, *Jigwei (Jw)*, *Lectra (Lc)*, *Bez różnicy (Br)*.
5. **Maskowanie pola „Kod produktu”** – obsługa automatycznego formatowania w locie do wzorca `XXX-XXXX-XXX`.
6. **Przycisk nawigacyjny** – pełnej szerokości przycisk „Strona główna” na samej górze interfejsu.

---

## 3. Kod Źródłowy Aplikacji

### 3.1. `app.py`
```python
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
        'strona': 'P', 'kolor_pisaka': 'Cz', 'maszyna': 'Br', 'kod_produktu': ''
    }

    if request.method == 'POST':
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material_kod = request.form.get('material_kod', '').strip().upper()
        dlugosc = request.form.get('dlugosc', '').strip()
        kod_produktu = request.form.get('kod_produktu', '').strip().upper()

        strona = request.form.get('strona', 'P')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material_kod': material_kod,
            'dlugosc': dlugosc, 'strona': strona, 'kolor_pisaka': kolor_pisaka,
            'maszyna': maszyna, 'kod_produktu': kod_produktu
        }

        # Weryfikacja materiału w pliku CSV
        materiały_dict = load_materials_dict()
        if material_kod in materiały_dict:
            material_nazwa_wyswietlana = materiały_dict[material_kod]
            
            opis_clean = remove_polish_chars(opis)
            material_kod_clean = remove_polish_chars(material_kod)

            # Schemat: ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb"
            wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material_kod_clean}_{opis_clean}_{maszyna}_{dlugosc}mb"
            if kod_produktu:
                wygenerowana_nazwa += f"_{kod_produktu}"
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
```

---

### 3.2. `templates/index.html`
```html
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.4 - Generator Nazw Plików Kroju</title>
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
            <h1>GNPK v0.4 Web - Generator Nazw Plików Kroju</h1>
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
                        <label><input type="radio" name="strona" value="L" {% if form.strona == 'L' %}checked{% endif %}> Lewa (L)</label>
                        <label><input type="radio" name="strona" value="P" {% if form.strona == 'P' %}checked{% endif %}> Prawa (P)</label>
                        <label><input type="radio" name="strona" value="O" {% if form.strona == 'O' %}checked{% endif %}> Obie (O)</label>
                    </div>
                </div>
                <div>
                    <label>Kolor pisaka:</label>
                    <div class="radio-group">
                        <label><input type="radio" name="kolor_pisaka" value="Cz" {% if form.kolor_pisaka == 'Cz' %}checked{% endif %}> Czarny (Cz)</label>
                        <label><input type="radio" name="kolor_pisaka" value="S" {% if form.kolor_pisaka == 'S' %}checked{% endif %}> Srebrny (S)</label>
                        <label><input type="radio" name="kolor_pisaka" value="N" {% if form.kolor_pisaka == 'N' %}checked{% endif %}> Niebieski (N)</label>
                        <label><input type="radio" name="kolor_pisaka" value="Z" {% if form.kolor_pisaka == 'Z' %}checked{% endif %}> Zielony (Z)</label>
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna CNC:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>Zund (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>Jigwei (Jw)</option>
                        <option value="Lc" {% if form.maszyna == 'Lc' %}selected{% endif %}>Lectra (Lc)</option>
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                    </select>
                </div>
                <div>
                    <label for="kod_produktu">Kod produktu:</label>
                    <input type="text" id="kod_produktu" name="kod_produktu" value="{{ form.kod_produktu }}" placeholder="001-0001-001" maxlength="12" oninput="maskKodProduktu(this)">
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
            // Jeśli użytkownik wpisze cyfrę na początku, automatycznie dodaj 'M'
            if (/^[0-9]/.test(val)) {
                val = 'M' + val;
            }
            // Zostawiamy 'M' na początku oraz cyfry
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
```

---

### 3.3. `templates/help.html`
```html
<!doctype html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GNPK v0.4 - Instrukcja</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>Instrukcja — GNPK v0.4 Web</h1>
            <a href="{{ url_for('index') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">← Powrót</a>
        </div>

        <p>Aplikacja generuje nazwę pliku kroju według schematu:</p>
        <pre>ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material_kod + "_" + opis + "_" + maszyna + "_" + dlugosc + "mb" + "_" + kod_produktu</pre>

        <h2>Pola formularza</h2>
        <ul>
            <li><strong>Ilość sztuk</strong> — liczba sztuk w układzie (wymagane).</li>
            <li><strong>Materiał (Kod)</strong> — kod materiału z pierwszej kolumny pliku <code>materiały.csv</code> formatowany automatycznie do maski <code>Mxxxx-xxx</code> (np. <code>M0101-001</code>). Wszystkie litery są zamieniane na wielkie.</li>
            <li><strong>Strona / Orientacja</strong> — L (Lewa), P (Prawa, domyślnie), O (Obie).</li>
            <li><strong>Kolor pisaka</strong> — Cz (Czarny), S (Srebrny), N (Niebieski), Z (Zielony).</li>
            <li><strong>Opis elementu</strong> — opcjonalny opis; polskie znaki są usuwane.</li>
            <li><strong>Maszyna CNC</strong> — Zu (Zund), Jw (Jigwei), Lc (Lectra), Br (Bez różnicy).</li>
            <li><strong>Długość układu (mb)</strong> — długość układu w metrach bieżących.</li>
            <li><strong>Kod produktu</strong> — opcjonalny kod w masce <code>xxx-xxxx-xxx</code>; dodawany na końcu nazwy po znaku „_”.</li>
        </ul>
    </div>
</body>
</html>
```
plan.md
Wyświetlam plan.md.