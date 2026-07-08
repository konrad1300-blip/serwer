Twój plik Markdown jest gotowy
[file-tag: code-generated-file-0-1783526279627935595]

import re

# Definiujemy treść pliku Markdown, uwzględniając strukturę projektu, kod app.py, index.html oraz opis działania.
markdown_content = """# Dokumentacja Projektu: GNPK Web (Generator Nazw Plików Kroju)

Projekt polega na migracji aplikacji desktopowej **GNPK v0.2** (oryginalnie napisanej w środowisku Lazarus / Free Pascal) do nowoczesnej aplikacji webowej uruchamianej na serwerze. Całość została oparta na mikro-frameworku **Flask (Python)** i w pełni dostosowana do stylistyki wizualnej dostarczonych plików (`style.css`).

---
# Dokumentacja Projektu: GNPK Web (Generator Nazw Plików Kroju)

Projekt polega na migracji aplikacji desktopowej **GNPK v0.2** (oryginalnie napisanej w środowisku Lazarus / Free Pascal) do nowoczesnej aplikacji webowej uruchamianej na serwerze. Całość została oparta na mikro-frameworku **Flask (Python)** i w pełni dostosowana do stylistyki wizualnej dostarczonych plików (`style.css`).

---

## 1. Struktura Katalogów Projektu

Aby aplikacja działała poprawnie w środowisku Flask, pliki na serwerze muszą być ułożone w następującej strukturze:

```text
moje_gnpk/
│
├── app.py                     # Główny serwer aplikacji (Python + Flask)
│
├── static/                    # Folder na zasoby statyczne
│   └── style.css              # Stylistyka (zapewniająca spójny wygląd)
│
└── templates/                 # Folder na szablony HTML (system Jinja2)
    ├── index.html             # Główny formularz generatora GNPK
    └── help.html              # Instrukcja / Strona pomocy# Dokumentacja Projektu: GNPK Web (Generator Nazw Plików Kroju)

Projekt polega na migracji aplikacji desktopowej **GNPK v0.2** (oryginalnie napisanej w środowisku Lazarus / Free Pascal) do nowoczesnej aplikacji webowej uruchamianej na serwerze. Całość została oparta na mikro-frameworku **Flask (Python)** i w pełni dostosowana do stylistyki wizualnej dostarczonych plików (`style.css`).



Przygotowałem plik dokumentacji o nazwie **`GNPK_Dokumentacja_Migracji.md`**, w którym zebrałem wszystkie ustalenia z naszej rozmowy.

### Co znajduje się w pliku:
1. **Struktura katalogów serwera:** Dokładny rozpis, gdzie w projekcie opartym na frameworku **Flask** mają się znaleźć pliki szablonów (`index.html`, `help.html`), a gdzie pliki zasobów statycznych (`style.css`).
2. **Pełny kod serwera (`app.py`):** Przepisana z Pascala logika biznesowa generatora nazw plików wraz z bezpiecznym filtrowaniem polskich znaków i zachowaniem wpisanych do formularza danych po odświeżeniu strony.
3. **Kod szablonu HTML (`index.html`):** Zmodyfikowany formularz, który idealnie mapuje wszystkie pola wyboru (ilość, materiał, maszyna, strona, kolor pisaka) z Twojej pierwotnej aplikacji okienkowej do struktury webowej z zachowaniem przesłanej wcześniej stylistyki CSS.
4. **Instrukcja uruchomienia:** Instrukcja krok po kroku opisująca instalację pakietów za pomocą `pip` oraz uruchomienie serwera na maszynie docelowej.


import os
from flask import Flask, render_template, request

app = Flask(__name__)

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

@app.route('/', methods=['GET', 'POST'])
def index():
    wygenerowana_nazwa = ""
    
    # Inicjalizacja słownika pustymi wartościami (zapobiega czyszczeniu formularza po wysłaniu)
    form_data = {
        'ilosc_szt': '', 'opis': '', 'material': '', 'wydajnosc': '', 'dlugosc': '',
        'strona': 'O', 'kolor_pisaka': 'Cz', 'maszyna': 'Br'
    }

    if request.method == 'POST':
        # 1. Pobieranie danych tekstowych wprowadzone przez użytkownika
        ilosc_szt = request.form.get('ilosc_szt', '').strip()
        opis = request.form.get('opis', '').strip()
        material = request.form.get('material', '').strip()
        wydajnosc = request.form.get('wydajnosc', '').strip()
        dlugosc = request.form.get('dlugosc', '').strip()
        
        # 2. Pobieranie opcji Radio / Select
        strona = request.form.get('strona', 'O')
        kolor_pisaka = request.form.get('kolor_pisaka', 'Cz')
        maszyna = request.form.get('maszyna', 'Br')

        # Zachowanie wprowadzonych wartości, aby użytkownik nie musiał wpisywać ich od nowa
        form_data = {
            'ilosc_szt': ilosc_szt, 'opis': opis, 'material': material, 
            'wydajnosc': wydajnosc, 'dlugosc': dlugosc, 'strona': strona, 
            'kolor_pisaka': kolor_pisaka, 'maszyna': maszyna
        }

        # 3. Filtrowanie polskich znaków w polach tekstowych podatnych na błędy maszynowe
        opis = remove_polish_chars(opis)
        material = remove_polish_chars(material)

        # 4. Dokładna konstrukcja nazwy pliku według schematu logicznego z kodu Pascal:
        # ilosc_szt + "szt_" + strona + "_" + kolor_pisaka + "_" + material + "_" + opis + "_Wyd" + wydajnosc + "%_" + maszyna + "_" + dlugosc + "mb"
        wygenerowana_nazwa = f"{ilosc_szt}szt_{strona}_{kolor_pisaka}_{material}_{opis}_Wyd{wydajnosc}%_{maszyna}_{dlugosc}mb"

    return render_template('index.html', nazwa=wygenerowana_nazwa, form=form_data)

@app.route('/pomoc')
def pomoc():
    return render_template('help.html')

if __name__ == '__main__':
    app.run(debug=True)



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
        button[type="submit"] {
            background-color: #2c3e50;
            color: white;
            border: none;
            border-radius: 50px;
            padding: 12px 20px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
        }
        button[type="submit"]:hover {
            background-color: #1a252f;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>GNPK v0.2 Web</h1>
            <a href="{{ url_for('pomoc') }}" class="server-home-btn" style="text-decoration: none; font-size: 0.9rem; color: #4a4a4a;">🛈 Instrukcja</a>
        </div>

        {% if nazwa %}
        <div class="result-box">
            <span style="font-size: 0.85rem; color: #7f8c8d; display: block; font-weight: normal; margin-bottom: 5px;">Wygenerowana nazwa pliku:</span>
            {{ nazwa }}
        </div>
        {% endif %}

        <form method="POST" action="/">
            
            <div class="form-group-row">
                <div>
                    <label for="ilosc_szt">Ilość sztuk:</label>
                    <input type="text" id="ilosc_szt" name="ilosc_szt" value="{{ form.ilosc_szt }}" required placeholder="np. 50">
                </div>
                <div>
                    <label for="material">Materiał:</label>
                    <input type="text" id="material" name="material" value="{{ form.material }}" required placeholder="np. Bawelna">
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
                    </div>
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label for="opis">Opis elementu:</label>
                    <input type="text" id="opis" name="opis" value="{{ form.opis }}" placeholder="np. Przod_kurtki">
                </div>
                <div>
                    <label for="wydajnosc">Wydajność (%):</label>
                    <input type="text" id="wydajnosc" name="wydajnosc" value="{{ form.wydajnosc }}" placeholder="np. 85">
                </div>
            </div>

            <div class="form-group-row">
                <div>
                    <label>Maszyna docelowa:</label>
                    <select name="maszyna" style="width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; margin-top: 5px;">
                        <option value="Br" {% if form.maszyna == 'Br' %}selected{% endif %}>Bez różnicy (Br)</option>
                        <option value="Zu" {% if form.maszyna == 'Zu' %}selected{% endif %}>ZUND (Zu)</option>
                        <option value="Jw" {% if form.maszyna == 'Jw' %}selected{% endif %}>JIGWEI (Jw)</option>
                    </select>
                </div>
                <div>
                    <label for="dlugosc">Długość układu (mb):</label>
                    <input type="text" id="dlugosc" name="dlugosc" value="{{ form.dlugosc }}" placeholder="np. 4.5">
                </div>
            </div>

            <div style="margin-top: 20px; text-align: center;">
                <button type="submit">Zatwierdź i generuj nazwę</button>
            </div>
        </form>
    </div>
</body>
</html>


### Zmiany:
Potrzebuje przyciski "Kopiuj nazwę", który skopiuje wygenerowaną nazwę jako string do schowka systemowego.
Materiał powinien byś rozwijana listą wyboru: pvc, freetarp, inny.
Domyślnie zaznaczona strona to Prawa.
Kolor pisacka: czarny, srebrny, niebieski, zielony.
Maszyna docelowa zmień na Maszyna CNC: Zund, Jigwei, Lectra, Bez różnicy.
Na zamej górze strony potrzebuje przycisk na szerokość DIV w tylu jak przycisk Zatwierź.. i podpięte do niego hiperlink :
 <a href="/" class="nav-btn">Strona główna</a>

Potrzebuje jeszcze jedno pole:"Kod produktu" z maską xxx-xxxx-xxx i ten kod ma być dodany po znaku _ na końcu wygenerowanego łańcucha nazwy pliku

