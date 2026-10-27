

Możesz zapisać poniższą treść jako plik **`PROJECT_PLAN.md`** lub **`README_DEV.md`** w głównym katalogu projektu.

---

# 📐 PLAN WYKONAWCZY PROJEKTU: Estymator Czasów Technologicznych Plandek (DXF + MES)

---

## 📋 1. Opis i Cel Projektu

### 1.1. Cel biznesowy

Głównym celem systemu jest automatyzacja i przyspieszenie procesu wyceny oraz przygotowania technologii dla nowych wyrobów (plandek PVC / materiałów powlekanych). Użytkownik (technolog) na podstawie **rysunków DXF** oraz **nowo nadanego kodu produktu** otrzymuje w kilka sekund:

1. Dopasowane **produkty analogiczne/podobne** wytwarzane w przeszłości.
2. Wyznaczone **przybliżone czasy operacji technologicznych** (krojenie, zgrzewanie, szycie, okucia, pakowanie itp.) wraz z bezpiecznymi przedziałami ufnoci (min–max).

### 1.2. Kluczowe obserwacje z analizy danych historycznych (MES)

Plik `Dane Mes DKR ZP ZAKOŃCZONE.xlsx` zawiera **113 058 rekordów** operacji technologicznych:

* **Kod Klienta:** Pierwsze 3 cyfry kodu produktu (np. `029` z kodu `029-0421-018`) jednoznacznie identyfikują klienta. Wyroby tego samego klienta wykazują wysokie podobieństwo pod względem konstrukcji, materiałów i standardu wykonania.
* **Powtarzalność kodów:** Kod produktu powtarza się w tabeli, ponieważ każde zlecenie produkcyjne (`ZP`) składa się z wielu jednostkowych procesów (`ProcesKod`).
* **Zmienność czasów:** Występuje wariancja czasu wykonania jednej sztuki (`CzasRealizacjiSztuka`) wynikająca z wielkości serii (`SztukWyrobu`) oraz warunków wykonania. Najbardziej miarodajną miarą statystyczną jest **mediana** czasów po odrzuceniu wartości skrajnych/błędnych.
* **Główne operacje:** Zgrzewanie, Krojenie, Szycie, Okucia, Kontrola, Pakowanie, Nadruk, Elementy.

---

## 🏗️ 2. Struktura Katalogów i Plików Projektu (`src` layout)

Projekt opiera się na **architekturze modułowej (Loose Coupling)**. Kod logiki biznesowej i procesorów jest całkowicie odizolowany od interfejsu graficznego.

```text
plandeka_estimator/
│
├── data/                             # Dane wejściowe, wyjściowe i przykładowe
│   ├── raw/                          # Surowy plik MES (Dane Mes DKR ZP ZAKOŃCZONE.xlsx)
│   ├── processed/                    # Wyczyszczona i skonsolidowana baza (baza_mes.sqlite)
│   └── samples/                      # Przykładowe pliki .dxf do testów i kalibracji
│
├── src/                              # Kod źródłowy aplikacji
│   ├── __init__.py
│   ├── config.py                     # Globalne konfigi (wagi podobieństwa, warstwy DXF, ścieżki)
│   ├── models.py                     # Klasy danych (Pydantic / Dataclasses)
│   │
│   ├── processors/                   # Samodzielne moduły przetwarzania (Procesory)
│   │   ├── __init__.py
│   │   ├── mes_processor.py          # [Procesor 1] Czyszczenie i agregacja bazy MES
│   │   ├── dxf_processor.py          # [Procesor 2] Ekstrakcja cech geometrycznych z DXF
│   │   ├── similarity_engine.py      # [Procesor 3] Silnik dopasowania wyrobów podobnych
│   │   └── time_estimator.py         # [Procesor 4] Wyliczanie czasów i przedziałów min-max
│   │
│   └── ui/                           # Warstwa Prezentacji (UI)
│       ├── __init__.py
│       └── app.py                    # Interfejs graficzny (Streamlit / Gradio / PySide6)
│
├── tests/                            # Testy jednostkowe (pytest)
│   ├── test_mes_processor.py
│   ├── test_dxf_processor.py
│   ├── test_similarity_engine.py
│   └── test_time_estimator.py
│
├── .gitignore
├── main.py                           # Glówny punkt wejścia (CLI / start UI)
├── requirements.txt                  # List bibliotek (ezdxf, pandas, openpyxl, pydantic itp.)
└── README.md                         # Dokumentacja użytkownika

```

---

## 📦 3. Klasy Danych i Kontrakty (`src/models.py`)

Aby uniknąć przekazywania nieustrukturyzowanych słowników, wszystkie procesory komunikują się za pomocą ścisłych modeli danych (dataclass / Pydantic).

```python
# src/models.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class DXFFeatures:
    """Reprezentuje wyekstrahowane cechy geometryczne z pliku DXF."""
    filename: str
    bounding_box_width_mm: float      # Szerokość gabarytowa [mm]
    bounding_box_height_mm: float     # Wysokość gabarytowa [mm]
    bounding_box_area_m2: float       # Pole prostokąta otaczającego [m2]
    total_cut_length_m: float         # Całkowita długość linii cięcia/obrysu [m]
    drawing_length_m: float           # Długość linii opisowych/rysujących [m]
    contours_count: int               # Liczba zamkniętych konturów/otworów
    layers_found: List[str]           # Lista wykrytych warstw w pliku DXF

@dataclass
class ProcessTimeStat:
    """Statystyki czasowe dla pojedynczego procesu technologicznego."""
    process_code: str                 # Kod procesu (np. ZGRZEWANIE)
    process_name: str                 # Nazwa procesu
    median_time_per_unit_min: float   # Mediana czasu [min/szt]
    min_time_per_unit_min: float      # Minimalny zanotowany czas
    max_time_per_unit_min: float      # Maksymalny zanotowany czas
    sample_count: int                 # Liczba prób/zleceń w bazie

@dataclass
class ProductProfile:
    """Profile wyrobu zgromadzonego w bazie wiedzy MES."""
    product_code: str                 # Pełny kod wyrobu (np. 029-0421-018)
    client_code: str                  # Kod klienta (np. 029)
    product_name: str                 # Nazwa wyrobu
    processes: Dict[str, ProcessTimeStat]  # Słownik procesów technologicznych

@dataclass
class MatchResult:
    """Wynik dopasowania produktu z bazy do zapytania użytkownika."""
    matched_product_code: str
    matched_product_name: str
    client_code: str
    similarity_score: float           # Wskaźnik podobieństwa (0.0 do 1.0 lub 0-100%)
    client_match: bool                # Czy kod klienta jest w 100% zgodny
    dxf_distance: float               # Odległość cech geometrycznych

```

---

## ⚙️ 4. Szczegółowa Specyfikacja Procesorów (Logika Biznesowa)

### 4.1. `src/processors/mes_processor.py` (Procesor 1: Baza MES)

**Zadanie:** Wczytanie pliku Excel, przefiltrowanie, skonsolidowanie czasów per kod produktu oraz zapisanie zoptymalizowanej bazy w formacie SQLite/Parquet dla szybkiego dostępu.

* **Logika przetwarzania:**
1. Filtruj rekordy z pustym `CzasRealizacjiSztuka` lub czasami $\le 0$.
2. Wyciągnij `KlientKod` jako pierwsze 3 znaki z `ProduktKod`.
3. Pogrupuj dane według `(ProduktKod, ProcesKod)`.
4. Wylicz medianę, minimum, maksimum oraz liczbę pomiarów dla każdego procesu.
5. Zapisz tabelę wyczyszczoną do pliku `data/processed/baza_mes.sqlite`.



---

### 4.2. `src/processors/dxf_processor.py` (Procesor 2: Analiza DXF)

**Zadanie:** Odczyt geometrii z pliku `.dxf` za pomocą biblioteki `ezdxf`.

* **Reguły analizy geometrii:**
1. **Warstwy:** Sprawdź warstwy standardowe dla urządzeń tnących (np. Lectra, Zund, Jigwei):
* Warstwy cięcia (obrys): np. `CUT`, `CIECIE`, `0`, `OUTLINE`.
* Warstwy rysowania/opisów: np. `DRAW`, `RYSOWANIE`, `PEN`, `TEXT`.


2. **Obliczenia:**
* Przeiteruj po elementach `LINE`, `LWPOLYLINE`, `POLYLINE`, `ARC`, `CIRCLE`.
* Oblicz skrajne współrzędne $(X_{min}, X_{max}, Y_{min}, Y_{max})$ -> Szerokość i Wysokość.
* Oblicz całkowitą długość odcinków i łuków na warstwach cięcia.





---

### 4.3. `src/processors/similarity_engine.py` (Procesor 3: Dopasowanie)

**Zadanie:** Wyszukanie najbardziej podobnych wyrobów w bazie historycznej.

* **Algorytm Hybrydowy:**
Podobieństwo całkowite $S$ wyliczane jest jako ważona kombinacja:

$$S = w_{klient} \cdot S_{klient} + w_{geom} \cdot S_{geom}$$


* **$S_{klient}$ (Zgodność klienta):**
* Jeśli pierwsze 3 cyfry nowego kodu zgadzają się z kodem wyrobu w bazie $\rightarrow S_{klient} = 1.0$.
* Jeśli się nie zgadzają $\rightarrow S_{klient} = 0.0$.


* **$S_{geom}$ (Podobieństwo geometrii):**
* Wyliczane z odległości euklidesowej znormalizowanych wektorów geometrii (powierzchnia BoundingBox, długość cięcia, proporcja boków):

$$d = \sqrt{ \left(\frac{\Delta A}{A_{max}}\right)^2 + \left(\frac{\Delta L}{L_{max}}\right)^2 + \left(\frac{\Delta R}{R_{max}}\right)^2 }$$


$$S_{geom} = \frac{1}{1 + d}$$




* **Wagi domyślne:** $w_{klient} = 0.4$, $w_{geom} = 0.6$.



---

### 4.4. `src/processors/time_estimator.py` (Procesor 4: Estymator Czasów)

**Zadanie:** Na podstawie wybranego wyrobu wzorcowego (lub ważonej średniej z Top-3 podobnych wyrobów) wyznaczenie prognozowanych czasów jednostkowych dla każdego z procesów.

* **Zasady estymacji:**
* Jeśli nowo podany plik DXF znacząco różni się rozmiarem/długością cięcia od wyrobu wzorcowego, skaluj czas krojenia stosunkiem długości cięcia:

$$t_{krojenie\_nowe} = t_{krojenie\_wzorzec} \cdot \left(\frac{L_{nowe}}{L_{wzorzec}}\right)$$


* Pozostałe procesy (np. Zgrzewanie, Kontrola, Pakowanie) przyjmują domyślnie wartości medianowe wzorca.
* Zwracana jest tabela ze szacowanym czasem oraz marginesem bezpieczeństwa (min–max).



---

## 🧪 5. Instrukcja Testowania i Weryfikacji (CLI & Pytest)

Każdy z procesorów posiada autonomiczny blok `if __name__ == "__main__":`, co umożliwia jego niezależną weryfikację bez konieczności uruchamiania całej aplikacji czy UI.

### 5.1. Weryfikacja manualna w konsoli (CLI)

1. **Test Procesora MES:**
```bash
python -m src.processors.mes_processor

```


*Oczekiwany wynik:* Komunikat o udanym przetworzeniu pliku Excel i utworzeniu bazy SQLite oraz podsumowanie ilości unikalnych produktów.
2. **Test Procesora DXF:**
```bash
python -m src.processors.dxf_processor data/samples/testowy.dxf

```


*Oczekiwany wynik:* Wypisanie w konsoli wymiarów (szerokość x wysokość), długości cięcia [m] i pola powierzchni [m²].
3. **Test Silnika Podobieństwa:**
```bash
python -m src.processors.similarity_engine --kod "029-0926-001" --dxf data/samples/testowy.dxf

```


*Oczekiwany wynik:* Tabela TOP-5 najbardziej podobnych wyrobów z bazy wraz z procentowym wskaźnikiem matchu.
4. **Test Estymatora Czasów:**
```bash
python -m src.processors.time_estimator --wzorzec "029-0421-018"

```


*Oczekiwany wynik:* Tabela z rozbiciem na procesy technologiczne, szacowanymi czasami i zakresem min-max.

### 5.2. Testy Automatyczne (`pytest`)

Uruchomienie kompletnego zestawu testów reguł biznesowych:

```bash
pytest -v

```

---

## 🖼️ 6. Szkic Interfejsu Użytkownika (UI Wireframe)

Aplikacja opiera się na przejrzystym dwuekranowym przepływie pracy.

```text
===================================================================================
                             EKRAN 1: DANE WEJŚCIOWE
===================================================================================
  [1] Wprowadź dane wyjściowe:
      • Plik DXF:          [ Wybierz plik .dxf... ]  (np. plandeka_stelaż.dxf)
      • Nowy Kod Produktu: [ 029-0926-001       ]
                           ↳ Rozpoznany Klient: "029" (Automatycznie)

                                [ 🔍 SZUKAJ PODOBNYCH ]
===================================================================================
                                        │
                                        ▼
===================================================================================
                         EKRAN 2: WYNIKI I ESTYMACJA CZASÓW
===================================================================================
  📐 CECHY GEOMETRYCZNE (z DXF):
  • Wymiary: 4200 x 2500 mm   • Długość cięcia: 18.5 m   • Pole otaczające: 10.5 m²

  🏆 RANKING DOPASOWANYCH WYROBÓW HISTORYCZNYCH:
  [X] 1. 029-0421-018 | Podobieństwo: 92% | Klient Zgodny | Nazwa: Alubag LEVEL 01
  [ ] 2. 029-0421-012 | Podobieństwo: 84% | Klient Zgodny | Nazwa: PVC PCM Tarpaulin
  [ ] 3. 063-0925-001 | Podobieństwo: 68% | Inny Klient   | Nazwa: Plandeka Płaska

  ⏱️ PRZEWIDYWANE CZASY PROCESÓW TECHNOLOGICZNYCH (dla zaznaczonego wzorca):
  ┌──────────────────────┬──────────────────┬──────────────────────────┐
  │ Proces               │ Szacowany Czas   │ Zakres z historii (MES)  │
  ├──────────────────────┼──────────────────┼──────────────────────────┤
  │ KROJENIE             │     1.8 min      │  (1.2 min – 2.4 min)     │
  │ ZGRZEWANIE           │    10.5 min      │  (8.0 min – 12.5 min)    │
  │ SZYCIE               │      ---         │  (Brak w technologii)    │
  │ KONTROLA             │     1.1 min      │  (0.9 min – 1.5 min)     │
  │ PAKOWANIE            │     0.8 min      │  (0.6 min – 1.2 min)     │
  ├──────────────────────┼──────────────────┼──────────────────────────┤
  │ SUMA CZASU / SZTUKA  │    14.2 min      │  (10.7 min – 17.6 min)   │
  └──────────────────────┴──────────────────┴──────────────────────────┘

                        [ 💾 ZAPISZ KARTĘ TECHNOLOGICZNĄ ]
===================================================================================

```

---

## 🚀 7. Instrukcja Krok-Po-Kroku Dla Programisty (Roadmap Implementacji)

Oto kolejność prac programistycznych:

1. **Krok 1: Inicjalizacja Środowiska**
* Utwórz strukturę katalogów (`src/`, `data/`, `tests/`).
* Zainstaluj wymagane biblioteki: `pandas`, `openpyxl`, `ezdxf`, `pydantic`, `pytest`, `streamlit` (lub `gradio`).


2. **Krok 2: Implementacja `src/models.py` i `src/config.py**`
* Zdefiniuj klasy danych dla DXF, profilu wyrobu i wyników dopasowania.
* Ustaw nazwy warstw DXF w pliku konfiguracyjnym.


3. **Krok 3: Budowa `src/processors/mes_processor.py**`
* Napisz skrypt przetwarzający plik `Dane Mes DKR ZP ZAKOŃCZONE.xlsx`.
* Przetestuj jego uruchomienie i upewnij się, że plik `data/processed/baza_mes.sqlite` generuje się prawidłowo.


4. **Krok 4: Budowa `src/processors/dxf_processor.py**`
* Zaimplementuj odczyt plików DXF przy użyciu `ezdxf`.
* Przetestuj na 2-3 plikach `.dxf` z produkcji plandek.


5. **Krok 5: Budowa `src/processors/similarity_engine.py**`
* Połącz wyekstrahowane dane DXF z bazą SQLite.
* Zaimplementuj formułę ważenia (kod klienta + geometria).


6. **Krok 6: Budowa `src/processors/time_estimator.py**`
* Dodaj wyliczanie czasów i przeskalowywanie krojeniowego czasu względem długości cięcia.


7. **Krok 7: Stworzenie Interfejsu UI (`src/ui/app.py`)**
* Zbuduj proste GUI (np. w Streamlit: `streamlit run src/ui/app.py`), łączące wszystkie procesory w jeden spójny system.



---

## 📝 Podsumowanie i Ocena Przepływu (Flow)

* **Sens Logiczny:** Zaproponowany przepływ jest w 100% spójny i odpowiada realiom pracy technologa w zakładzie produkcji plandek. Pozwala zamienić ręczne szukanie historycznych zleceń w arkuszach Excel na natychmiastowe, automatyczne dopasowanie.
* **Potencjalne Miejsca Zatrzymania Użytkownika:**
1. **Nowy Klient:** Jeśli wprowadzone zostaną pierwsze 3 cyfry klienta, którego nie ma jeszcze w bazie MES, wskaźnik $S_{klient}$ wyniesie $0$. *Rozwiązanie:* Program przełączy się wówczas automatycznie na dopasowanie wyłącznie po geometrii DXF.
2. **Błędy/Brak Warstw w DXF:** Jeśli rysunek DXF zostanie zapisany bez zachowania standardowych warstw cięcia/obrysu, parser może zwrócić długość cięcia równą 0. *Rozwiązanie:* Program powinien umożliwiać ręczny wybór warstwy cięcia z rozwijanej listy w interfejsie użytkownika.