# Poprawki dokumentacji: manual_page.py + README.md + INSTRUKCJA_UZYTKOWNIKA.md

## 1. Krótkie podsumowanie

Trzy poprawki dokumentacyjne, w kolejności od najmniejszej do największej:

- **`manual_page.py`** — 3 miejsca opisują nieaktualny algorytm (stan przed E1). Po naprawie user widzi w instrukcji to samo, co robi silnik: asymetria braku BOM (zapytanie → renormalizacja, kandydat → neutralne 0.5).
- **`README.md`** — pełna regeneracja. Sekcja „Zasady algorytmów" pokazuje teraz formułę 3-składnikową z BOM, struktura projektu uwzględnia wszystkie pliki UI, dodana sekcja o konfiguracji `.env` i bezpieczeństwie finansów BOM.
- **`INSTRUKCJA_UZYTKOWNIKA.md`** — pełna regeneracja do wersji 2.0, wszystkie 9 rozdziałów z spisu treści (obecnie urwane po rozdz. 2).

---

## 2. Tabela plików

| # | Plik | Status | Zmiana |
|---|---|---|---|
| 1 | `src/ui/manual_page.py` | ✏️ ZMODYFIKOWANY | 3 poprawki opisu trybów (zakładki „Silnik dopasowania" i „BOM i materiały") |
| 2 | `README.md` | ✏️ ZMODYFIKOWANY | Pełna regeneracja: formuła 3-składnikowa, struktura projektu, konfiguracja, bezpieczeństwo |
| 3 | `INSTRUKCJA_UZYTKOWNIKA.md` | ✏️ ZMODYFIKOWANY | Pełna regeneracja 2.0 — 9 rozdziałów |

---

## 3. Kompletne pliki

### 📄 `src/ui/manual_page.py` — ✏️ ZMODYFIKOWANY

**Uwaga:** plik jest długi (głównie treść markdowna). Zmiany są w **trzech** miejscach: zakładka 3 (opis trybu 1 i trybu 2), zakładka 4 (sekcja „Kiedy BOM nie wchodzi do dopasowania"). Wszystkie inne sekcje bez zmian.

```python
"""Strona „📖 Instrukcja Użytkownika" (Streamlit).

Zawiera pełny podręcznik, taby tematyczne oraz wyszukiwarkę haseł.
Wydzielona z `app.py`, żeby uniknąć przepisywania treści przy każdej
regeneracji głównego pliku UI.
"""
import pandas as pd
import streamlit as st

from src.config import (
    BASE_DIR,
    BOM_ALPHA_PRECYZJA,
    BOM_MAX_DEPTH,
    BOM_NEUTRAL_SIMILARITY,
    DRAWING_SCALE,
    WEIGHT_BOM,
    WEIGHT_CLIENT,
    WEIGHT_GEOM,
)
from src.ui.helpers import get_db_stats


def render_manual_page():
    """Renderuje stronę z podręcznikiem użytkownika i skróconą dokumentacją."""
    st.markdown("## 📖 Podręcznik i Instrukcja Użytkownika")
    st.caption("Kompletna dokumentacja systemu, opis algorytmów, wytyczne CAD/CAM i rozwiązywanie problemów.")

    stats = get_db_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Wyroby w bazie", f"{stats['products']:,}")
    m2.metric("👥 Klienci", f"{stats['clients']:,}")
    m3.metric("📐 Pliki DXF", f"{stats['dxf_count']:,}")
    m4.metric("📏 Skala rysunku", f"1:{int(DRAWING_SCALE)}")

    manual_path = BASE_DIR / "INSTRUKCJA_UZYTKOWNIKA.md"
    manual_content = ""
    if manual_path.exists():
        manual_content = manual_path.read_text(encoding="utf-8")

    with st.container(border=True):
        st.markdown("**🔍 Szybkie wyszukiwanie w podręczniku**")
        search_query = st.text_input(
            "Szukaj hasła:",
            placeholder="np. 'skalowanie', 'warstwy', 'BOM', 'F5', 'percentyl'...",
            label_visibility="collapsed",
        )
        if search_query.strip():
            matching_lines = [
                line.strip() for line in manual_content.split("\n")
                if search_query.lower() in line.lower() and line.strip()
            ]
            if matching_lines:
                st.success(f"Znaleziono **{len(matching_lines)}** dopasowań dla frazy **'{search_query}'**:")
                st.markdown("\n".join(f"• {line}" for line in matching_lines[:15]))
            else:
                st.warning(f"Nie znaleziono dopasowań dla frazy **'{search_query}'**.")

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🚀 Szybki start",
        "📐 Geometria DXF",
        "🧠 Silnik dopasowania",
        "🧩 BOM i materiały",
        "⏱️ Estymacja czasów",
        "✂️ Czas kroju",
        "📄 Pełny tekst",
    ])

    # ==========================================================================
    # ZAKŁADKA 1: SZYBKI START
    # ==========================================================================
    with tab1:
        st.markdown("### 🚀 Jak zacząć w 5 krokach")
        st.caption("Standardowy cykl pracy technologa od wgrania rysunku do gotowej karty technologicznej.")

        steps = [
            ("Wybierz tryb", "📐 DXF + kod (dokładniejszy) lub 🔢 Tylko kod (bez rysunku).", "🎯"),
            ("Wgraj plik DXF / podaj kod", "Wybierz z próbek, wgraj plik, albo podaj sam kod `XXX-YYYY-ZZZ`.", "📁"),
            ("Uruchom analizę", "Kliknij **SZUKAJ PODOBNYCH I ESTYMUJ CZASY**. System przeszuka bazę i pokaże TOP-5.", "🔍"),
            ("Wybierz wzorzec", "Domyślnie wybrany TOP-1. Możesz kliknąć inny z rankingu.", "🏆"),
            ("Zapisz kartę", "Pobierz JSON / CSV lub zapisz na serwerze w `data/processed/karty_technologiczne/`.", "💾"),
        ]

        for i, (title, desc, icon) in enumerate(steps, 1):
            with st.container(border=True):
                cols = st.columns([0.06, 1])
                cols[0].markdown(f"<h2 style='margin:0;'>{icon}</h2>", unsafe_allow_html=True)
                cols[1].markdown(f"**Krok {i}. {title}**")
                cols[1].caption(desc)

        st.divider()
        st.markdown("### 🎯 Kiedy który tryb?")

        st.markdown("""
System sam dobiera poziom szczegółowości dopasowania, zależnie od tego, co masz do dyspozycji:

| Masz do dyspozycji | System użyje |
|---|---|
| Kod + **DXF** + BOM w bazie | Trzy składowe: **klient + geometria + BOM** |
| Kod + BOM (bez DXF) | Dwie składowe: **klient + BOM** |
| Sam kod (brak DXF i BOM-u) | Trzy składowe: **klient + data (MMYY) + wiarygodność** |
        """)

        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("**📐 DXF + kod**")
                st.caption(
                    "Masz rysunek DXF. Algorytm łączy podobieństwo geometrii "
                    "(pole, długość cięcia, proporcja boków), zgodność klienta i strukturę BOM. "
                    "Estymacja uwzględnia **skalowanie krojenia** po długości ścieżki."
                )
                st.markdown("Użyj przy: **nowej ofercie z rysunkiem**, wycenie dokładnej.")
        with c2:
            with st.container(border=True):
                st.markdown("**🔢 Tylko kod**")
                st.caption(
                    "Brak rysunku. System najpierw sprawdza, czy kod ma **BOM**. "
                    "Jeśli tak — ranking po **kliencie + BOM-ie**. "
                    "Jeśli nie — fallback po **kliencie + dacie (MMYY) + wiarygodności**. "
                    "Estymacja **bez skalowania geometrii** — wynik przybliżony."
                )
                st.markdown("Użyj przy: **szybkiej wycenie, gdy rysunek jeszcze nie dotarł**.")

        st.info(
            "💡 **Wagi algorytmu są na suwakach w pasku bocznym.** Domyślnie: "
            f"`w_klient={WEIGHT_CLIENT:.2f}`, `w_bom={WEIGHT_BOM:.2f}`, `w_geom={WEIGHT_GEOM:.2f}`. "
            "**F5 / restart przywraca wartości domyślne** — nie musisz nic klikać, żeby cofnąć zmiany."
        )

        st.divider()
        st.markdown("### 📥 Rozszerzanie bazy rysunków DXF")

        st.markdown("""
Baza rysunków rośnie o pliki `.dxf`, które zgromadzisz w katalogu `dxf/` w projekcie.

**Scenariusz:** dostajesz nowy rysunek od klienta:

1. W kalkulatorze wybierz tryb **📐 DXF + kod** i wgraj plik (opcja „Prześlij własny plik .DXF").
2. Zaznacz checkbox **📥 Dodaj do bazy rysunków (katalog `dxf/`)**.
3. Aplikacja zweryfikuje nazwę pliku — musi zaczynać się od maski **`AIxxx-xxxx-xxx`**
   (np. `AI029-0421-013.dxf`). Pliki niezgodne z maską **nie zostaną zapisane**.
4. Jeśli nazwa jest poprawna, aplikacja sprawdzi SHA-256 zawartości:
   - jeśli plik już jest w bazie — pokaże komunikat i użyje istniejącej kopii,
   - jeśli nie — skopiuje plik do `dxf/` (przy kolizji nazwy dopisze `_2`, `_3`, …).
5. W pasku bocznym kliknij **📐 Reindeksuj pliki DXF**, aby przeliczyć cechy i zapisać je do SQLite.
        """)

        st.divider()
        st.markdown("### 📥 Aktualizacja danych")

        with st.container(border=True):
            st.markdown("**📡 Pobierz MES z ERP**")
            st.caption(
                "Bezpośrednie połączenie z ERP XL. Tryb przyrostowy: 90 dni + rekordy niezamknięte. "
                "Pobiera dane MES do pamięci, aktualizuje bazę SQLite i automatycznie reindeksuje pliki DXF."
            )
            st.markdown("➡️ Pasek boczny → **📡 Pobierz MES z ERP**")

        with st.container(border=True):
            st.markdown("**📦 Pobierz BOM z ERP**")
            st.caption(
                "Pełny pull widoku `_im_mm_kalkulacja_Excel`. Aktualizuje tabele "
                "`bom_technologies` i `bom_items` w bazie SQLite. Wymagane, żeby ranking "
                "uwzględniał składową BOM."
            )
            st.markdown("➡️ Pasek boczny → **📦 Pobierz BOM z ERP**")

        with st.container(border=True):
            st.markdown("**📐 Reindeksuj pliki DXF**")
            st.caption(
                "Przelicza cechy geometrii wszystkich plików `.dxf` z katalogu `dxf/` i zapisuje je "
                "do bazy SQLite — bez pełnego pullu z ERP."
            )
            st.markdown("➡️ Pasek boczny → **📐 Reindeksuj pliki DXF**")

        with st.container(border=True):
            st.markdown("**🔒 Finanse BOM — odblokowanie hasłem**")
            st.caption(
                "Stawki i wartości PLN w BOM są domyślnie ukryte. Wpisz hasło w sekcji "
                "**🔒 Finanse BOM** w pasku bocznym, żeby je odblokować. "
                "**F5 / restart kasuje odblokowanie** — trzeba wpisać hasło ponownie."
            )
            st.markdown("➡️ Pasek boczny → **🔒 Finanse BOM**")

    # ==========================================================================
    # ZAKŁADKA 2: GEOMETRIA DXF
    # ==========================================================================
    with tab2:
        st.markdown("### 📐 Geometria DXF — co czytamy z rysunku")
        st.caption(
            f"Wszystkie wymiary w interfejsie podawane są jako **rzeczywiste** "
            f"(po korekcie skali **1:{int(DRAWING_SCALE)}**)."
        )

        st.markdown("#### Kluczowe parametry")
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("**📏 Wymiary gabarytowe (X × Y)**")
                st.caption("Skrajne wymiary prostokąta otaczającego detal.")
            with st.container(border=True):
                st.markdown("**📐 Pole otaczające**")
                st.caption("Pole prostokąta otaczającego detal [m²].")
            with st.container(border=True):
                st.markdown("**✂️ Długość cięcia**")
                st.caption("Sumaryczna długość ścieżek na warstwach cięcia — kluczowa dla czasu kroju.")
        with c2:
            with st.container(border=True):
                st.markdown("**🖊️ Długość rysowania**")
                st.caption("Linie pisaka, opisy, linie zaginania.")
            with st.container(border=True):
                st.markdown("**🔢 Liczba konturów**")
                st.caption("Liczba elementów geometrycznych w rysunku.")
            with st.container(border=True):
                st.markdown("**⚖️ Proporcja boków (aspect ratio)**")
                st.caption("Stosunek szerokości do wysokości — do identyfikacji pasów.")

        st.divider()
        st.markdown("#### 📚 Standardowe warstwy CAD/CAM")

        layers_df = pd.DataFrame({
            "Przeznaczenie": ["Linie cięcia (nóż / laser)", "Pisak, opisy, zaginanie"],
            "Domyślne nazwy w DXF": [
                "CUT, INTERNAL_CUT, CIECIE, OUTLINE, OBRYS, NOTCH, 0, KONTUR",
                "PEN, DRAW, RYSOWANIE, TEXT, PISAK, OPIS, ZAGINANIE, 8",
            ],
            "Wizualizacja": ["🔴 Czerwony (gruba linia)", "🔵 Niebieski (cienka linia)"],
        })
        st.dataframe(layers_df, hide_index=True, width="stretch")

        with st.expander("⚙️ Konfiguracja niestandardowych warstw"):
            st.markdown("""
Jeśli Twoje rysunki używają innych nazw warstw (np. `KONTUR_1`, `NOZ_2`), możesz je dopisać:

1. Otwórz **pasek boczny**.
2. W polu **Warstwy cięcia** wpisz dodatkowe nazwy oddzielone przecinkami.
3. Zatwierdź i wróć do kalkulatora — nowe warstwy będą traktowane jako linie cięcia.

**Przykład:** `CUT, OBRYS, KONTUR_1, NOZ_2`
            """)

        st.divider()
        st.markdown("#### 🖼️ Jak sprawdzić, czy rysunek jest poprawny?")
        with st.container(border=True):
            st.markdown("""
Po wgraniu pliku DXF w kalkulatorze zobaczysz **podgląd 2D** po prawej stronie:

- **Czerwone grube linie** = warstwy cięcia (nóż / laser). Jeśli nic nie ma czerwonego — dodaj nazwy warstw cięcia w pasku bocznym.
- **Niebieskie cienkie linie** = pisak, opisy, zaginanie.
- **Puste tło bez linii** = rysunek w przestrzeni layoutu zamiast modelu, albo brak encji — sprawdź eksport z CAD.
            """)

    # ==========================================================================
    # ZAKŁADKA 3: SILNIK DOPASOWANIA
    # ==========================================================================
    with tab3:
        st.markdown("### 🧠 Silnik dopasowania — trzy tryby")
        st.caption(
            "System automatycznie wybiera tryb zależnie od dostępnych danych. "
            "Wagi są wspólne dla wszystkich trybów — sterujesz nimi w pasku bocznym."
        )

        with st.container(border=True):
            st.markdown("#### 📊 Hierarchia trybów")
            st.markdown("""
| Priorytet | Tryb | Kiedy używany |
|---|---|---|
| 1 | **DXF + kod + BOM** | Wgrałeś rysunek, w bazie jest BOM dla zapytania i kandydatów |
| 2 | **Kod + BOM** | Tryb tylko-kod, zapytanie ma BOM, co najmniej jeden kandydat ma BOM |
| 3 | **Kod + data + reliability** | Fallback: brak BOM po którejkolwiek stronie |
            """)

        st.divider()
        st.markdown("#### 📐 Tryb 1: DXF + kod + BOM")
        st.latex(
            r"S = \frac{w_{klient} \cdot S_{klient} + w_{geom} \cdot S_{geom} + w_{bom} \cdot S_{bom}}"
            r"{w_{klient} + w_{geom} + w_{bom}}"
        )
        st.markdown(r"""
- $S_{klient}$ — **1.0** gdy klient zgodny (pierwsze 3 cyfry kodu), inaczej **0.0**.
- $S_{geom} = \dfrac{1}{1 + d}$ — im mniejsza odległość geometryczna, tym wyżej.
- $S_{bom}$ — kompozycja precyzji i struktury materiałowej (szczegóły w zakładce **🧩 BOM i materiały**).

**Semantyka braku BOM jest asymetryczna:**
- brak BOM u **zapytania** → wagi renormalizowane do `(w_klient : w_geom)`,
- brak BOM u **kandydata** (a zapytanie ma BOM) → kandydat dostaje **neutralne $S_{bom}$ = 0,5**, wagi pozostają pełne. Dzięki temu kandydat bez danych nie jest karany zerem, ale też nie wygrywa z kandydatem, który ma realny, choć słabo dopasowany BOM.
        """)

        with st.container(border=True):
            st.markdown("#### 🔢 Tryb 2: Kod + BOM (bez DXF)")
            st.latex(r"S = \frac{w_{klient} \cdot S_{klient} + w_{bom} \cdot S_{bom}}{w_{klient} + w_{bom}}")
            st.markdown(r"""
- Klient jest już przefiltrowany w SQL, więc $S_{klient} = 1.0$ dla wszystkich kandydatów.
- W praktyce ranking sortuje się **po podobieństwie BOM-u**.
- **Kandydaci bez BOM-u wchodzą do rankingu** z neutralnym $S_{bom}$ = 0,5 — nie są wykluczani. W praktyce wygrywają z kandydatami o słabo dopasowanym BOM-ie, ale przegrywają z kandydatami o dobrze dopasowanym.
- **Bez skalowania krojenia** — estymacja czasów to mediany wzorca.
            """)

        with st.container(border=True):
            st.markdown("#### 🔢 Tryb 3: Kod + data + reliability (fallback)")
            st.latex(r"S = 0{,}55 \cdot S_{klient} + 0{,}35 \cdot S_{data} + 0{,}10 \cdot rel")
            st.markdown(r"""
- $S_{klient}$ — **1.0** gdy klient zgodny (w tym trybie zawsze, bo filtrujemy po kliencie).
- $S_{data} = \dfrac{1}{1 + \Delta_{mc} / 12}$ — im mniejsza różnica miesięcy, tym wyżej.
- $rel = \dfrac{\log(1 + \text{próby})}{\log(1 + \text{max prób})}$ — premia za wyroby z historią w MES.

Uruchamiany, gdy zapytanie nie ma BOM-u **lub** żaden kandydat go nie ma — nie ma płaszczyzny porównania BOM.
            """)

        st.info(
            "💡 **Interpretacja struktury kodu `XXX-YYYY-ZZZ`:** "
            "`XXX` = klient · `YYYY` = `MMYY` (miesiąc + rok) · `ZZZ` = numer kolejny "
            "produktu klienta w danym miesiącu."
        )

        st.divider()
        st.markdown("#### 🎚️ Wagi i suwaki")

        st.markdown(
            "Trzy wagi sterują dopasowaniem. **Zawsze sumują się do 1.0.**\n\n"
            "| Waga | Default | Rola |\n"
            "|---|---|---|\n"
            f"| `w_klient` | **{WEIGHT_CLIENT:.2f}** | Zgodność kodu klienta (pierwsze 3 cyfry). |\n"
            f"| `w_geom` | **{WEIGHT_GEOM:.2f}** | Podobieństwo geometrii (pole, długość cięcia, proporcja). |\n"
            f"| `w_bom` | **{WEIGHT_BOM:.2f}** | Podobieństwo struktury materiałowej. |\n\n"
            "W sidebarze są **dwa aktywne suwaki**: `w_klient` i `w_bom`. "
            "Trzecia waga (`w_geom`) jest **wyliczana**: `w_geom = 1 − w_klient − w_bom`.\n\n"
            "🔄 **F5 / restart przywraca wartości domyślne** — nie musisz nic klikać. "
            "Defaulty są zapisane w `config.py`."
        )

        st.divider()
        st.markdown("#### 🔄 Adaptacja wag dla nowego klienta")

        st.info(
            "Jeśli w bazie **nie ma żadnego wyrobu** danego klienta, system automatycznie "
            "zeruje wagę klienta — dopasowanie działa wtedy wyłącznie **po geometrii i BOM-ie**. "
            "Pozostałe wagi są renormalizowane proporcjonalnie."
        )

    # ==========================================================================
    # ZAKŁADKA 4: BOM I MATERIAŁY
    # ==========================================================================
    with tab4:
        st.markdown("### 🧩 BOM i materiały")
        st.caption(
            "BOM (Bill of Materials) to lista materiałów i półproduktów, z których "
            "powstaje wyrób. Dane pobierane są z widoku ERP `_im_mm_kalkulacja_Excel`."
        )

        st.divider()
        st.markdown("#### 📚 Kategorie materiałów")

        st.markdown("""
Każdy materiał ma kod zaczynający się od prefiksu `Mxx` (trzy znaki), który określa kategorię:

| Prefiks | Kategoria | Przykładowe materiały |
|---|---|---|
| `M01` | 🧵 **Tkaniny powlekane** | Tkaniny PVC, MEHLER, SIOEN, Heytex |
| `M02` | 🔩 **Okucia, oczka, haki** | Oczka plandekowe, haki, washers |
| `M03` | 🔗 **Klamry, sprzączki** | Klamry grzechotkowe, sprzączki |
| `M04` | 🎗️ **Taśmy, pasy** | Taśmy poliestrowe, webbing |
| `M05` | 🧵 **Zamki, nici, sznurki** | Zamki YKK, nici Serafil |
| `M06` | 🪢 **Gumy, liny, taśmy namiotowe** | Guma spandor, liny stalowe, taśmy Keder |
| `M07` | 🖨️ **Folie, nadruki** | Folie samoprzylepne, ORACAL |
| `M08` | 🏷️ **Etykiety** | Etykiety produktowe, oznakowanie |
| `M09` | 🔗 **Tulejki, nity, akcesoria** | Tulejki, nity, magnesy |
| `M10` | 🧱 **Elementy sztywne** | Płyty HDPE, rury aluminiowe, formatek |
| `M11` | 🎒 **Pasy z klamrą, torby** | Ratchet tie down, pasy z klipsem |
| `M12` | 🧶 **Materiały specjalne** | Odyssey, nylon |
| `M14` | ⚙️ **Różne** | Pozostałe pozycje |
| `M15` | 💧 **Wskaźniki, pochłaniacze** | Wskaźniki wilgoci, DESI PAK |
        """)

        st.divider()
        st.markdown("#### 🌳 Struktura BOM — drzewo i spłaszczanie")

        st.markdown("""
BOM może zawierać **półprodukty** — wyrób mający własną technologię. Wtedy tworzy się **drzewo**:

029-0421-018 (Plandeka Alubag)
├── M0107-011 Tkanina MEHLER 30 m²
├── 029-0421-020 (Półprodukt) ×2
│ ├── M0107-009 Tkanina inna 5 m²
│ ├── M0403-011 Taśma 043 3 m
│ └── M0202-038 Oczko owalne 4 szt
└── M0202-017 Oczko okrągłe 12 szt

Silnik dopasowania używa **spłaszczonej** postaci BOM-u — zamienia drzewo na listę liści
(`Mxxxx-xxx`) z ilościami przemnożonymi przez wszystkie poziomy. Powyższy BOM spłaszczony:

| Kod | Ilość |
|---|---|
| `M0107-011` | 30 m² |
| `M0107-009` | 5 × 2 = **10 m²** |
| `M0403-011` | 3 × 2 = **6 m** |
| `M0202-038` | 4 × 2 = **8 szt** |
| `M0202-017` | 12 szt |

Dzięki temu dwa wyroby z identycznymi fizycznymi materiałami, ale różnymi kodami
półproduktów, są porównywane po **rzeczywistym składzie**.
        """)

        st.info(
            f"⚙️ **Zabezpieczenia spłaszczania:** limit głębokości = **{BOM_MAX_DEPTH} poziomy**, "
            "ochrona przed cyklami (jeśli A zawiera B, a B zawiera A), oraz zachowanie półproduktu "
            "jako „czarnej skrzynki\", gdy jego BOM-u brakuje w bazie. "
            "Dzięki temu silnik nie zapętli się i nie przeładuje pamięci."
        )

        st.divider()
        st.markdown("#### 📐 Składowa `S_bom` — jak liczymy podobieństwo BOM-ów")

        st.markdown(
            "`S_bom` to **kompozycja precyzji i struktury**:\n\n"
            f"$$S_{{bom}} = {BOM_ALPHA_PRECYZJA:.2f} \\cdot S_{{precyzja}} "
            f"+ {1 - BOM_ALPHA_PRECYZJA:.2f} \\cdot S_{{struktura}}$$\n\n"
            "**Precyzja** — obecność tych samych kodów `Mxxxx-xxx` (waga 0.75) "
            "+ zgodność ilości (waga 0.25):\n\n"
            r"$$S_{precyzja} = 0{,}75 \cdot \text{Jaccard}(kody) + 0{,}25 \cdot \overline{sim_{ilość}}$$"
            "\n\n**Struktura** — podobieństwo udziałów kategorii (M01..M15) w sumie ilości:\n\n"
            r"$$S_{struktura} = \max\left(0,\ 1 - \frac{\text{L1}(udziały)}{2}\right)$$"
        )

        with st.expander("🔢 Przykład liczbowy"):
            st.markdown("""
**Zapytanie** ma kody: `M0107-011 (30 m²)`, `M0202-038 (56 szt)`, `M0403-011 (20 m)`.

**Kandydat A** ma te same kody z tymi samymi ilościami → `S_bom = 1.0`.

**Kandydat B** ma inne kody, ale te same kategorie (`M01`, `M02`, `M04`) → precyzja = 0, struktura = 1, `S_bom = 0.30`.

Kandydat A wygrywa zdecydowanie, ale B **nie dostaje zera** — ma szansę zaistnieć, gdy brak lepszych kandydatów.
            """)

        st.divider()
        st.markdown("#### 🎯 Kiedy BOM nie wchodzi do dopasowania?")

        st.markdown(
            "**Dwa przypadki, gdy BOM nie wchodzi do wyniku ze swoją pełną wagą:**\n\n"
            "1. **Zapytanie nie ma BOM-u** (nowy kod bez technologii w ERP) → wagi "
            "**renormalizowane** do `(w_klient : w_geom)`. BOM nie jest w ogóle oceniany.\n\n"
            "2. **Kandydat nie ma BOM-u, ale zapytanie ma** → kandydat dostaje "
            f"**neutralne $S_{{bom}}$ = {BOM_NEUTRAL_SIMILARITY:.1f}** (środek skali), "
            "wagi pozostają pełne. Dzięki temu nie jest karany zerem, ale też nie "
            "wygrywa z kandydatem, który ma realny, choć słabo dopasowany BOM.\n\n"
            "**Dodatkowo**, w trybie tylko-kod (bez DXF): gdy zapytanie ma BOM, ale "
            "**żaden** kandydat go nie ma — cała ścieżka wpada w fallback (data + reliability), "
            "bo nie ma płaszczyzny porównania BOM-owego.\n\n"
            "> 💡 **W obu trybach (DXF + kod oraz kod + BOM) semantyka braku BOM jest taka sama** — "
            "kandydat bez BOM jest traktowany neutralnie, nie jest wykluczany."
        )

        st.divider()
        st.markdown("#### 📦 Aktualizacja BOM z ERP")

        st.markdown("""
**Pasek boczny → 📦 Pobierz BOM z ERP**

- Zawsze **pełny pull** (widok `_im_mm_kalkulacja_Excel` nie ma znacznika przyrostowego).
- Dla każdego rdzenia wybierana jest **najnowsza rewizja** (`Rxx`) i w niej **najnowsza wersja** (`Vxx`).
- Duplikaty po `PTZ_Kod` są **sumowane** (ilości i wartości).
- Zapis do tabel `bom_technologies` i `bom_items` w tej samej bazie SQLite co MES.
- **Czas aktualizacji** widoczny pod przyciskiem.

⚠️ **Uwaga o kodach bez formatu `XXX-XXXX-XXX`:** BOM przetwarza wyłącznie rdzenie
w formacie `XXX-XXXX-XXX` (np. `029-0421-018`). Kody tekstowe typu `PROF-SHOPPEN 102260`,
`PAKOWANIE VESTAS CHINA` itp. są **pomijane** — nie da się ich dopasować do kodu MES.
W konsoli pojawi się komunikat „Pominięto N wierszy bez rozpoznanego rdzenia kodu".

⚠️ Bez pobranego BOM-u ranking działa, ale **bez składowej BOM** — silnik wpada w fallback.
        """)

        st.info(
            "💡 **Przeglądarka BOM** — osobna strona **📦 BOM Wyrobu** w menu po lewej. "
            "Pokazuje rozbicie materiałów po kategoriach, półprodukty w expanderach i sumę wartości."
        )

        st.divider()
        st.markdown("#### 🔒 Ochrona danych finansowych")

        st.markdown("""
Stawki i wartości PLN w BOM **są domyślnie ukryte**. Aby je zobaczyć:

1. Pasek boczny → sekcja **🔒 Finanse BOM**.
2. Wpisz hasło skonfigurowane przez administratora w pliku `.env` (`BOM_FINANCE_PASSWORD`).
3. Po odblokowaniu widoczne są kolumny `Stawka [PLN]` i `Wartość [PLN]` na stronie **📦 BOM Wyrobu**,
   a także metryki `Wartość materiałów` i `SUMA WARTOŚCI MATERIAŁÓW`.

**Zabezpieczenia:**
- **F5 / restart** kasuje odblokowanie — trzeba wpisać hasło ponownie.
- Brak hasła w `.env` = dane finansowe trwale ukryte (bezpieczeństwo domyślne).
- Hasło porównywane jest w stałym czasie (`secrets.compare_digest`).
        """)

    # ==========================================================================
    # ZAKŁADKA 5: ESTYMACJA CZASÓW
    # ==========================================================================
    with tab5:
        st.markdown("### ⏱️ Estymacja czasów — skąd bierzemy wartości")
        st.caption(
            "Wycena opiera się na rzeczywistych danych z systemu MES (zakończone operacje)."
        )

        with st.container(border=True):
            st.markdown("#### 📊 Dlaczego mediana, a nie średnia?")
            st.markdown("""
W produkcji plandek średnia arytmetyczna bywa **zaburzona** przez:
- prototypy jednosztukowe (operator uczy się wyrobu),
- pomyłki w rejestracji czasu na terminalu,
- awarie maszyn i przerwy.

**Mediana** odrzuca wartości skrajne i wskazuje **realny, powtarzalny czas** seryjnego wykonania.
            """)

        st.divider()
        st.markdown("#### 📈 Percentyle — rozkład rzeczywistych odbić")
        st.caption("Pokazują, jak rozkładają się rzeczywiste czasy MES wokół mediany.")

        p1, p2, p3 = st.columns(3)
        p1.metric("📉 Percentyl 25", "Wariant szybki", "produkt wykonany sprawnie")
        p2.metric("📊 Percentyl 50", "Wartość środkowa", "= mediana")
        p3.metric("📈 Percentyl 75", "Wariant ostrożny", "produkt wykonany wolniej")

        st.divider()
        st.markdown("#### ⚙️ Skalowanie czasu krojenia")

        st.caption(
            "Skalowanie działa **tylko w trybie DXF + kod**. "
            "W trybach „kod + BOM\" i „kod + data\" brak skalowania — bierzemy medianę wzorca wprost."
        )
        with st.container(border=True):
            st.latex(r"t_{nowe} = t_{wzorzec} \cdot \frac{L_{nowe}}{L_{wzorzec}}")
            st.markdown(r"""
**Przykład:** wzorzec kroił się 5 min przy ścieżce 2 m. Nowy wyrób ma ścieżkę 4 m.

Współczynnik skali: $k = 4 / 2 = 2{,}0$. Nowy czas krojenia: $t = 5 \cdot 2{,}0 = 10$ min.
            """)

    # ==========================================================================
    # ZAKŁADKA 6: CZAS KROJU
    # ==========================================================================
    with tab6:
        st.markdown("### ✂️ Kalkulator czasu kroju — ZUND / LECTRA / JIGWEI")
        st.caption(
            "Niezależny kalkulator przewidywanego czasu kroju, oparty na mnożnikach "
            "z kalkulatora v0.15."
        )

        with st.container(border=True):
            st.markdown("#### 📐 Wzór")
            st.latex(r"t_{min} = \frac{L_{mm} \cdot mck \cdot mr}{60}")
            st.markdown("""
gdzie:
- $L_{mm}$ — **surowa** długość ścieżki z DXF [mm] (bez korekty skali 1:10),
- $mck$ — mnożnik czystego kroju dla maszyny,
- $mr$ — mnożnik ramki = **1,08748**.
            """)

        st.markdown("#### 📋 Mnożniki maszyn")
        machines_df = pd.DataFrame({
            "Maszyna": ["🛠️ ZUND", "🛠️ LECTRA", "🛠️ JIGWEI"],
            "Mnożnik (mck)": ["0,08307067", "0,090474006", "0,101171631"],
            "Typowe zastosowanie": [
                "Cutter CNC — najszybszy nóż",
                "Cutter CNC — średnia prędkość",
                "Cutter CNC — najwolniejszy nóż",
            ],
        })
        st.dataframe(machines_df, hide_index=True, width="stretch")

        st.info(
            "💡 Wyniki kalkulatora kroju pokazują się **bezpośrednio pod cechami "
            "geometrycznymi** na stronie kalkulatora (tylko tryb DXF + kod) oraz w Przeglądarce Bazy MES."
        )

    # ==========================================================================
    # ZAKŁADKA 7: PEŁNY TEKST
    # ==========================================================================
    with tab7:
        st.markdown("### 📄 Pełna treść podręcznika inżynierskiego")
        st.caption("Dokumentacja źródłowa z pliku `INSTRUKCJA_UZYTKOWNIKA.md`.")

        if manual_content:
            st.download_button(
                label="📥 Pobierz instrukcję jako plik Markdown",
                data=manual_content,
                file_name="INSTRUKCJA_UZYTKOWNIKA_PLANDEKI.md",
                mime="text/markdown", width="stretch",
            )
            st.divider()
            with st.container(border=True):
                st.markdown(manual_content)
        else:
            st.warning(
                "Plik `INSTRUKCJA_UZYTKOWNIKA.md` nie istnieje w katalogu głównym projektu. "
                "Wgraj go, aby zobaczyć pełną treść."
            )
```

**Punktowe zmiany w `manual_page.py`:**

- **Import:** dodany `BOM_NEUTRAL_SIMILARITY` z `src.config` (do wstawienia wartości w treści markdowna).
- **Zakładka 1 (Szybki start):** dodana czwarta karta „🔒 Finanse BOM — odblokowanie hasłem" (żeby użytkownik wiedział, gdzie szukać hasła).
- **Zakładka 3 (Tryb 1: DXF + kod + BOM):** zamiast zdania o renormalizacji przy braku BOM po którejkolwiek stronie — dwupunktowy opis asymetrii (zapytanie vs. kandydat) z wartością `S_bom = 0.5` dla braku BOM u kandydata.
- **Zakładka 3 (Tryb 2: Kod + BOM):** zdanie „Kandydaci bez BOM-u są pomijani" → „Kandydaci bez BOM-u wchodzą z neutralnym 0,5".
- **Zakładka 3 (Tryb 3):** drobne doprecyzowanie, że fallback uruchamia się gdy zapytanie nie ma BOM **lub** żaden kandydat go nie ma.
- **Zakładka 4 (Kiedy BOM nie wchodzi):** przepisana — dwa przypadki zamiast trzech, opis zgodny z E1.
- **Zakładka 4 (Aktualizacja BOM):** dodane ostrzeżenie o pomijaniu kodów bez formatu `XXX-XXXX-XXX`.
- **Zakładka 4:** dodana sekcja „🔒 Ochrona danych finansowych".

---

### 📄 `README.md` — ✏️ ZMODYFIKOWANY

```markdown
# 📐 Estymator Czasów Technologicznych Plandek (DXF + MES + BOM)

System automatycznej wyceny, dopasowania wyrobów analogicznych i estymacji czasów procesów technologicznych (krojenie, zgrzewanie, szycie, okucia, kontrola, pakowanie itp.) na podstawie rysunków technicznych **DXF**, danych historycznych z bazy **MES** oraz struktury materiałowej **BOM** z ERP XL.

---

## 🚀 Szybki start

### 1. Wymagania i instalacja

Aplikacja wymaga środowiska Python 3.10+ oraz bibliotek wymienionych w `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Konfiguracja `.env`

Skopiuj `.env.example` → `.env` i uzupełnij wartości:

```bash
cp .env.example .env
chmod 600 .env   # na Linuxie
```

Wymagane zmienne:
- `ERP_SERVER`, `ERP_DATABASE`, `ERP_DRIVER` — dane serwera SQL Server,
- `ERP_UID`, `ERP_PWD` — login i hasło do ERP XL,
- `BOM_FINANCE_PASSWORD` — hasło do odblokowania stawek/wartości PLN w UI.

⚠️ Plik `.env` **nie może** trafić do repozytorium. Sprawdź `.gitignore`.

### 3. Budowa i przygotowanie bazy wiedzy MES

Pełna inicjalizacja bazy (MES + BOM + indeksacja DXF) jest możliwa z UI (przyciski
w sidebarze). W CLI:

```bash
python -m src.processors.mes_processor
python -m src.processors.bom_processor
python -m src.processors.dxf_processor data/samples/testowy.dxf --index-all
```

lub w skrócie:
```bash
python main.py --rebuild-db
```

### 4. Uruchomienie aplikacji z interfejsem graficznym (UI)

```bash
streamlit run src/ui/app.py
```
lub:
```bash
python main.py --ui
```

---

## 🖥️ Uruchamianie w wierszu poleceń (CLI)

Każdy moduł aplikacji może działać jako w pełni autonomiczny program w konsoli:

### 1. Analiza pliku DXF (Procesor 2)
```bash
python -m src.processors.dxf_processor data/samples/testowy.dxf
```

### 2. Wyszukiwanie wyrobów analogicznych (Procesor 3)
```bash
python -m src.processors.similarity_engine --kod "029-0926-001" --dxf data/samples/testowy.dxf
```

### 3. Estymacja czasów technologicznych (Procesor 4)
```bash
python -m src.processors.time_estimator --wzorzec "029-0421-018"
```
Z uwzględnieniem skalowania czasu cięcia na podstawie geometrii DXF:
```bash
python -m src.processors.time_estimator --wzorzec "029-0421-018" --dxf data/samples/testowy.dxf --kod "029-0926-001"
```

### 4. Kompletny potok przetwarzania (Main CLI)
```bash
python main.py --kod "029-0926-001" --dxf data/samples/testowy.dxf
```

---

## 🧪 Testy automatyczne

Kompletny zestaw testów jednostkowych (pytest):

```bash
pytest -v
```

---

## 🏗️ Architektura i struktura projektu

```text
plandeka_estimator/
│
├── data/
│   ├── raw/                          # Surowy plik MES (CSV/XLSX z ERP)
│   ├── processed/                    # Baza SQLite (baza_mes.sqlite) + karty technologiczne
│   │   └── karty_technologiczne/     # Zapisane karty (JSON)
│   └── samples/                      # Pliki DXF do testów i kalibracji
│
├── dxf/                              # Baza rysunków DXF (indeksowana do SQLite)
│
├── src/
│   ├── config.py                     # Konfiguracja globalna (wagi, warstwy, ścieżki, hasła)
│   ├── models.py                     # Modele danych (DXFFeatures, MatchResult, BOMItem, itp.)
│   ├── db_metadata.py                # Metadata aplikacji (last_refresh_at, itp.)
│   │
│   ├── processors/
│   │   ├── data_source.py            # [Procesor 0] Abstrakcja źródeł (CSV, XLSX, DataFrame, ERP)
│   │   ├── mes_processor.py          # [Procesor 1] Czyszczenie i agregacja bazy MES
│   │   ├── dxf_processor.py          # [Procesor 2] Ekstrakcja cech geometrycznych z DXF
│   │   ├── similarity_engine.py      # [Procesor 3] Silnik dopasowania wyrobów podobnych
│   │   ├── time_estimator.py         # [Procesor 4] Wyliczanie czasów i przedziałów min-max
│   │   ├── bom_processor.py          # [Procesor 5] Przetwarzanie BOM z ERP + spłaszczanie
│   │   └── cutting_calculator.py     # Kalkulator czasu kroju (ZUND/LECTRA/JIGWEI)
│   │
│   └── ui/
│       ├── app.py                    # Główny plik UI + sidebar + router
│       ├── helpers.py                # Współdzielone helpery UI (get_db_stats, render_zp_table)
│       ├── manual_page.py            # Strona 📖 Instrukcja Użytkownika
│       ├── bom_page.py               # Strona 📦 BOM Wyrobu
│       ├── comparison_page.py        # Strona ⚖️ Porównywarka Wyrobów
│       └── database_browser_page.py  # Strona 📊 Przeglądarka Bazy MES
│
├── tests/                            # Testy jednostkowe (pytest)
│   ├── test_mes_processor.py
│   ├── test_dxf_processor.py
│   ├── test_similarity_engine.py
│   ├── test_bom_similarity.py
│   ├── test_time_estimator.py
│   ├── test_cutting_calculator.py
│   ├── test_data_source.py
│   ├── test_erp_source.py
│   └── test_incremental.py
│
├── main.py                           # Punkt wejścia (CLI / start UI)
├── requirements.txt
├── .env.example                      # Szablon konfiguracji (bez prawdziwych danych)
├── README.md
└── INSTRUKCJA_UZYTKOWNIKA.md
```

---

## 🧠 Tryby dopasowania

Silnik automatycznie wybiera tryb w zależności od dostępnych danych:

| Priorytet | Tryb | Warunek | Wzór |
|---|---|---|---|
| 1 | **DXF + kod + BOM** | Wgrano DXF, zapytanie i przynajmniej jeden kandydat mają BOM | $S = \frac{w_{k} S_{k} + w_{g} S_{g} + w_{b} S_{b}}{w_k + w_g + w_b}$ |
| 2 | **Kod + BOM** | Tryb tylko-kod, zapytanie ma BOM i przynajmniej jeden kandydat ma BOM | $S = \frac{w_k S_k + w_b S_b}{w_k + w_b}$ |
| 3 | **Kod + data + reliability** | Fallback: zapytanie nie ma BOM lub żaden kandydat nie ma BOM | $S = 0{,}55 S_k + 0{,}35 S_{data} + 0{,}10 rel$ |

### Semantyka braku BOM (wariant B — spójny we wszystkich trybach)

- **Brak BOM u zapytania** → składowa BOM pomijana, wagi renormalizowane.
- **Brak BOM u kandydata** (zapytanie ma BOM) → kandydat dostaje **neutralne $S_{bom} = 0{,}5$**, wagi pozostają pełne. Nie jest karany zerem, ale też nie wygrywa z kandydatami o realnym BOM-ie.

---

## 🧮 Zasady algorytmów

### 1. Dopasowanie hybrydowe (3-składnikowe)

$$S = \frac{w_{klient} \cdot S_{klient} + w_{geom} \cdot S_{geom} + w_{bom} \cdot S_{bom}}{w_{klient} + w_{geom} + w_{bom}}$$

- **$S_{klient} = 1{,}0$** jeśli pierwsze 3 cyfry kodu (kod klienta) są zgodne, w przeciwnym razie **0,0**. Gdy klient nie ma żadnych wyrobów w bazie — waga klienta jest zerowana.
- **$S_{geom} = \frac{1}{1 + d}$**, gdzie $d$ to euklidesowa odległość znormalizowanych wektorów geometrii (pole, długość cięcia, proporcja boków).
- **$S_{bom}$** — kompozycja precyzji (Jaccard + sim ilości) i struktury (udziały kategorii M01..M15):
  $$S_{bom} = 0{,}70 \cdot S_{precyzja} + 0{,}30 \cdot S_{struktura}$$
  gdzie:
  - $S_{precyzja} = 0{,}75 \cdot \text{Jaccard}(kody) + 0{,}25 \cdot \overline{sim_{ilość}}$,
  - $S_{struktura} = \max\left(0,\ 1 - \frac{\text{L1}(udziały)}{2}\right)$,
  - $sim_{ilość}(q, c) = \frac{1}{1 + |q - c| / \max(q, c)}$.

**Wagi domyślne:** `w_klient = 0,15`, `w_geom = 0,45`, `w_bom = 0,40`. Sumują się do 1,0.

Sterowanie w sidebarze: dwa suwaki (`w_klient`, `w_bom`). Trzecia waga wyliczana: `w_geom = 1 − w_klient − w_bom`. **F5 / restart przywraca defaulty** z `config.py`.

### 2. Spłaszczanie BOM (dla silnika)

BOM wyrobu jest drzewem (półprodukty mają własne technologie). Silnik porównuje **liście**:

- Rekurencja przez `_flatten_recursive()` — mnożenie ilości przez wszystkie poziomy.
- Limit głębokości: `BOM_MAX_DEPTH = 3`.
- Ochrona przed cyklem: `visited` set — jeśli kod już odwiedzony na ścieżce, nie wchodzimy ponownie.
- Półprodukt bez własnego BOM-u → „czarna skrzynka" (`is_semiproduct=True`).
- Duplikaty `ptz_kod` **sumowane** (fix z E1 — wcześniej nadpisywane).

### 3. Skalowanie czasów operacji krojenia

Tylko w trybie **DXF + kod**. Czas krojenia skalowany stosunkiem długości cięcia:

$$t_{krojenie\_nowe} = t_{krojenie\_wzorzec} \cdot \frac{L_{nowe}}{L_{wzorzec}}$$

Pozostałe procesy technologiczne — mediany wzorca wprost. W trybach „kod + BOM" i „kod + data" **brak skalowania** (brak geometrii nowego wyrobu).

### 4. Czas kroju maszynowego

$$t_{min} = \frac{L_{mm} \cdot mck \cdot mr}{60}$$

gdzie:
- $L_{mm}$ — surowa długość ścieżki DXF [mm],
- $mck$ — mnożnik czystej maszyny (ZUND: 0,0831 / LECTRA: 0,0905 / JIGWEI: 0,1012),
- $mr$ — mnożnik ramki = 1,08748.

### 5. Dlaczego mediana, nie średnia?

W produkcji plandek średnia bywa zaburzona przez prototypy, pomyłki terminalowe i awarie. Mediana odrzuca outliery i pokazuje realny, powtarzalny czas.

---

## 🔒 Bezpieczeństwo i dane wrażliwe

- **Hasła i poświadczenia** trzymane wyłącznie w `.env` (nie commitowane).
- **BOM — dane finansowe** (stawka, wartość PLN) ukryte w UI za hasłem `BOM_FINANCE_PASSWORD`. Odblokowanie działa w sesji, **F5 kasuje**.
- **W bazie SQLite** stawki i wartości są zapisane jawnie — ochrona dotyczy wyłącznie warstwy prezentacji. Jeśli dane finansowe mają być chronione przed lokalnym dostępem, trzeba szyfrować kolumny lub trzymać je w osobnej bazie z ACL.
- **ERP** — hasło w `.env`, nigdy w kodzie. `pyodbc` importowany lokalnie (`_connect()`), żeby aplikacja działała bez sterownika ODBC w trybie CSV/DataFrame.

---

## 📋 Znane ograniczenia

- **BOM obsługuje wyłącznie kody `XXX-XXXX-XXX`** (np. `029-0421-018`). Kody tekstowe (`PROF-SHOPPEN 102260`, `PAKOWANIE VESTAS CHINA` itp.) są pomijane przy budowie bazy BOM — nie da się ich dopasować do MES.
- **Wgranie DXF do bazy** wymaga maski nazwy `AIxxx-xxxx-xxx` (np. `AI029-0421-013.dxf`). Wrażliwe na wielkość liter.
- **Dane finansowe w bazie** są jawne. Ochrona to tylko UI.
- **Bulk SELECT BOM** przy 100+ kandydatach — obecnie N zapytań (optymalizacja: jedno zapytanie z `IN (...)`).

---

## 📄 Licencja i kontakt

Projekt wewnętrzny HansAA. W razie pytań — dział IT/technologii.
```

**Punktowe zmiany w `README.md`:**

- Tytuł: dodane „+ BOM".
- Sekcja „Konfiguracja `.env`" — nowa, wyjaśnia wszystkie zmienne i bezpieczeństwo.
- Sekcja „Budowa bazy" — dodane `bom_processor`.
- Struktura projektu — pełna (wszystkie pliki UI, db_metadata.py, karty_technologiczne, `data_source.py`, `cutting_calculator.py`).
- Sekcja „Tryby dopasowania" — tabela 3 trybów z wzorami + wyjaśnienie wariantu B (brak BOM u kandydata → 0,5).
- Sekcja „Zasady algorytmów" — pełna formuła 3-składnikowa, wzory BOM, spłaszczanie, skalowanie, kalkulator kroju, wyjaśnienie mediany.
- Sekcja „Bezpieczeństwo i dane wrażliwe" — nowa.
- Sekcja „Znane ograniczenia" — nowa.

---

### 📄 `INSTRUKCJA_UZYTKOWNIKA.md` — ✏️ ZMODYFIKOWANY

Pełna regeneracja do wersji **2.0** — wszystkie 9 rozdziałów z spisu treści.

```markdown
# 📖 PODRĘCZNIK I INSTRUKCJA UŻYTKOWNIKA
## Estymator Czasów Technologicznych Plandek (DXF + MES + BOM)
**Wersja:** 2.0 (Produkcyjna)  
**Data:** 2026-10-13  
**Przeznaczenie:** Dział Technologii, Dział Wycen i Ofertowania, Planowanie Produkcji  

---

## 📑 SPIS TREŚCI
1. [Wprowadzenie i Cel Systemu](#1-wprowadzenie-i-cel-systemu)
2. [Szybki Start – Jak wycenić wyrób w 5 krokach](#2-szybki-start)
3. [Architektura Danych i Standardy Nazewnictwa](#3-architektura-danych-i-standardy-nazewnictwa)
4. [Przewodnik po Interfejsie Aplikacji](#4-przewodnik-po-interfejsie-aplikacji)
5. [Matematyka i Logika Algorytmów](#5-matematyka-i-logika-algorytmów)
6. [Rozwiązywanie Problemów (Troubleshooting)](#6-rozwiązywanie-problemów)
7. [Dobre Praktyki Przygotowania Rysunków DXF](#7-dobre-praktyki-przygotowania-rysunków-dxf)
8. [Najczęściej Zadawane Pytania (FAQ)](#8-najczęściej-zadawane-pytania-faq)
9. [Historia zmian](#9-historia-zmian)

---

## 1. Wprowadzenie i Cel Systemu

System **Estymator Czasów Technologicznych Plandek** to narzędzie inżynierskie wspomagające pracę technologów i kosztorysantów w zakładach produkcji wyrobów z technicznych tkanin powlekanych PVC, plandek samochodowych, pokrowców, zbiorników elastycznych, worków przemysłowych (Alubag) oraz konstrukcji membranowych.

### Jaki problem rozwiązuje?
Przygotowanie oferty cenowej lub nowej technologii wymagało dotychczas:
- ręcznego przeglądania tysięcy historycznych zleceń,
- szukania „na oko" wyrobów o zbliżonej wielkości i konstrukcji,
- ręcznego przeliczania czasów operacji jednostkowych,
- ryzyka niedoszacowania czasochłonności (straty finansowe).

System automatyzuje ten proces:
1. Pobiera plik **CAD DXF** nowego wyrobu (lub tylko kod).
2. Dokonuje ekstrakcji cech geometrycznych (obrys, pole, długość cięcia, linie zaginania).
3. Przeszukuje bazę wiedzy MES i znajduje **najbardziej zbliżone technologicznie wyroby z przeszłości** — po geometrii, zgodności klienta i strukturze materiałowej (BOM).
4. Wylicza **czasy jednostkowe każdego procesu** (z automatycznym przeskalowaniem krojenia) oraz widełki min–max i percentyle.
5. Umożliwia wygenerowanie i zapisanie **Karty Technologicznej**.

---

## 2. Szybki Start

### 2.1. Cykl pracy w 5 krokach

1. **Wybierz tryb** — 📐 DXF + kod (dokładniejszy) lub 🔢 Tylko kod (bez rysunku).
2. **Wgraj plik DXF** (opcjonalnie) i **wpisz kod produktu** w formacie `XXX-YYYY-ZZZ`.
3. **Kliknij SZUKAJ PODOBNYCH I ESTYMUJ CZASY**. System przeszuka bazę i pokaże TOP-5 dopasowanych wyrobów.
4. **Wybierz wzorzec** — domyślnie TOP-1, ale możesz kliknąć inny z rankingu.
5. **Zapisz kartę** — pobierz JSON / CSV lub zapisz na serwerze.

### 2.2. Wymagania wstępne

- Baza MES pobrana z ERP (**📡 Pobierz MES z ERP** w sidebarze).
- Baza BOM pobrana z ERP (**📦 Pobierz BOM z ERP**) — bez tego ranking nie uwzględni struktury materiałowej.
- Pliki DXF zaindeksowane (**📐 Reindeksuj pliki DXF**) — jeśli chcesz tryb DXF + kod.

### 2.3. Struktura kodu produktu

**Rdzeń:** `XXX-YYYY-ZZZ`, gdzie:
- `XXX` — kod klienta (np. `029`),
- `YYYY` — `MMYY` (miesiąc + rok, np. `0926` = wrzesień 2026),
- `ZZZ` — numer kolejny produktu klienta w danym miesiącu.

**Sufiks rewizji/wersji:** `_RxxVxx` (dwucyfrowy, np. `_R01V02`). System zawsze wybiera **najnowszą rewizję, w niej najnowszą wersję**. Brak sufiksu → traktujemy jako rewizja 0, wersja 0.

**Kody materiałów:** `Mxxxx-xxx` (np. `M0107-011`) — niepowtarzalne, niezmienne, z różnymi jednostkami (`szt`, `M2`, `MTR`, `m`, `komplet`, `set`).

---

## 3. Architektura Danych i Standardy Nazewnictwa

### 3.1. Trzy źródła danych

| Źródło | Zawartość | Jak aktualizować |
|---|---|---|
| **MES** | Rzeczywiste czasy operacji z zakończonych zleceń | 📡 Pobierz MES z ERP (przyrostowo: 90 dni + rekordy niezamknięte) |
| **BOM** | Struktura materiałowa wyrobów (z widoku `_im_mm_kalkulacja_Excel`) | 📦 Pobierz BOM z ERP (pełny pull) |
| **DXF** | Geometria rysunków (pole, długość cięcia, kontur) | 📐 Reindeksuj pliki DXF po wgraniu nowych plików |

### 3.2. Źródło danych MES

Widok ERP: `_ha_bk_dkr_mes_v2`. Kluczowe kolumny:
- `ProduktKod`, `ProcesKod`, `ProcesNazwa`, `ProduktNazwa`,
- `CzasRealizacjiSztuka` — czas jednostkowy [min],
- `PZL_Status` — `zamknięte` / inne (reagregacja przyrostowa),
- `ZP`, `ZS`, `DziałZP`, `SztukWyrobu` — do drill-down w analizie ZP-ków.

### 3.3. Parametry geometryczne z DXF

| Parametr | Znaczenie |
|---|---|
| Wymiar X, Y (mm) | Skrajne wymiary prostokąta otaczającego detal |
| Pole otaczające (m²) | Pole prostokąta |
| Długość cięcia (m) | Suma ścieżek na warstwach cięcia — kluczowa dla krojenia |
| Długość rysowania (m) | Pisak, opisy, linie zaginania |
| Liczba konturów | Liczba elementów geometrycznych |
| Proporcja boków | Szerokość / wysokość |

⚠️ **Skala rysunku: 1:10.** W UI pokazujemy wartości rzeczywiste (×10 dla wymiarów, ×100 dla pola), ale kalkulator kroju używa **surowych mm z DXF** (bez korekty).

### 3.4. Standardy warstw CAD/CAM

| Przeznaczenie | Domyślne nazwy |
|---|---|
| Linie cięcia | `CUT`, `INTERNAL_CUT`, `CIECIE`, `OUTLINE`, `OBRYS`, `NOTCH`, `0`, `KONTUR` |
| Pisak, opisy, zaginanie | `PEN`, `DRAW`, `RYSOWANIE`, `TEXT`, `PISAK`, `OPIS`, `ZAGINANIE`, `8` |

Niestandardowe warstwy możesz dopisać w sidebarze (pole **Warstwy cięcia**, oddzielone przecinkami).

### 3.5. Struktura katalogów

```
data/
├── raw/                    # Surowy plik MES (CSV/XLSX z ERP)
├── processed/              # baza_mes.sqlite + karty_technologiczne/
└── samples/                # Przykładowe pliki DXF

dxf/                        # Baza rysunków (indeksowana do SQLite)
```

---

## 4. Przewodnik po Interfejsie Aplikacji

### 4.1. Pasek boczny (sidebar)

Sekcje sidebaru od góry:

1. **📊 Baza Wiedzy MES** — metryki: liczba wyrobów, klientów, zaindeksowanych DXF.
2. **🌐 Źródło danych ERP XL** — przyciski: 📡 Pobierz MES z ERP, 🔌 Testuj, 📦 Pobierz BOM z ERP.
3. **📐 Indeksacja DXF** — przycisk 📐 Reindeksuj pliki DXF.
4. **⚙️ Parametry Algorytmu** — suwaki `w_klient` i `w_bom` (+ wyliczana `w_geom`).
5. **✂️ Warstwy Cięcia** — pole tekstowe z listą warstw cięcia.
6. **🔒 Finanse BOM** — pole hasła do odblokowania stawek i wartości PLN.

**🔄 F5 / restart przywraca wszystkie wartości domyślne** — wagi, odblokowanie finansów, ustawienia.

### 4.2. Ekran 1: Dane wejściowe

- **Tryb wyszukiwania:** radio 📐 DXF + kod / 🔢 Tylko kod.
- **Wybór pliku DXF:** z gotowych próbek (`data/samples/`) lub upload.
  - Checkbox „📥 Dodaj do bazy rysunków" — kopia pliku do `dxf/` (SHA-256 dedup).
  - Wymagana maska nazwy: `AIxxx-xxxx-xxx` (np. `AI029-0421-013.dxf`).
- **Kod produktu:** format `XXX-YYYY-ZZZ`.
- **Rozpoznanie klienta:** system sprawdza, czy klient istnieje w bazie MES — pokazuje ✅ / ⚠️.

### 4.3. Ekran 2: Wyniki geometrii i podgląd 2D

Dla trybu DXF + kod:
- Wymiary gabarytowe (rzeczywiste, po korekcie skali),
- Pole otaczające (rzeczywiste),
- Długość cięcia (rzeczywista),
- Liczba konturów, wykryte warstwy,
- Podgląd 2D (czerwone linie = cięcie, niebieskie = pisak),
- **Kalkulator kroju maszynowego** (ZUND / LECTRA / JIGWEI) — surowe mm × `mck` × `mr` / 60.

### 4.4. Ekran 3: Ranking dopasowania

Tabela TOP-5 dopasowanych wyrobów z:
- kodem i nazwą wyrobu,
- wynikiem podobieństwa (%),
- zgodnością klienta,
- (DXF mode) odległością geometryczną, długością cięcia, liczbą plików DXF.

Wybierasz wzorzec radioboxem — system użyje go do estymacji.

### 4.5. Ekran 4: Estymacja czasów i skalowanie

Tabela procesów z:
- szacowanym czasem (mediana + ewentualne skalowanie krojenia),
- percentylami P25 / P50 / P75,
- zakresem min–max z MES,
- informacją o metodzie („Mediana (N prób)" lub „⚡ Skalowane (×k)").

Suma czasów jednostkowych + metryki zbiorcze.

### 4.6. Ekran 5: Zapis karty

- **📥 Pobierz Kartę Technologiczną (JSON)** — pełny eksport,
- **📥 Pobierz Zestawienie Czasów (CSV)** — tylko tabela,
- **💾 ZAPISZ KARTĘ NA DYSKU** — do `data/processed/karty_technologiczne/`.

### 4.7. Pozostałe strony

- **⚖️ Porównywarka Wyrobów** — grupa (A) vs. jeden wyrób (B). Mediana z median grupy, percentyle, drill-down per wyrób, analiza ZP. Ostrzeżenie przy rozrzucie geometrycznym > 50%.
- **📦 BOM Wyrobu** — przeglądarka BOM. Materiały grupowane po kategoriach (M01..M15 + SEMI + OTHER). Stawki/wartości PLN ukryte do odblokowania hasłem.
- **📊 Przeglądarka Bazy MES** — eksploracja wyrobów, procesów, geometrii DXF, drill-down do odbić ZP-ków (z filtrem Dział ZP).
- **📖 Instrukcja Użytkownika** — ten podręcznik.

---

## 5. Matematyka i Logika Algorytmów

### 5.1. Trzy tryby dopasowania

| Priorytet | Tryb | Warunek |
|---|---|---|
| 1 | DXF + kod + BOM | Wgrano DXF, w bazie BOM dla zapytania i kandydatów |
| 2 | Kod + BOM | Tryb tylko-kod, zapytanie i przynajmniej jeden kandydat mają BOM |
| 3 | Kod + data + reliability | Fallback: brak BOM po którejkolwiek stronie |

### 5.2. Tryb 1: DXF + kod + BOM

$$S = \frac{w_{klient} S_{klient} + w_{geom} S_{geom} + w_{bom} S_{bom}}{w_{klient} + w_{geom} + w_{bom}}$$

- $S_{klient}$ — 1,0 gdy klient zgodny (3 pierwsze cyfry), inaczej 0,0.
- $S_{geom} = \frac{1}{1 + d}$ — im mniejsza odległość, tym wyżej.
- $S_{bom}$ — patrz 5.5.

**Wagi domyślne:** `w_klient = 0,15`, `w_geom = 0,45`, `w_bom = 0,40`.

### 5.3. Tryb 2: Kod + BOM (bez DXF)

$$S = \frac{w_{klient} \cdot 1{,}0 + w_{bom} S_{bom}}{w_{klient} + w_{bom}}$$

Klient wstępnie przefiltrowany w SQL — dla wszystkich kandydatów $S_{klient} = 1{,}0$. Ranking sortuje się po $S_{bom}$.

### 5.4. Tryb 3: Kod + data + reliability (fallback)

$$S = 0{,}55 \cdot S_{klient} + 0{,}35 \cdot S_{data} + 0{,}10 \cdot rel$$

- $S_{data} = \frac{1}{1 + \Delta_{mc} / 12}$ — im bliżej daty produkcji, tym wyżej.
- $rel = \frac{\log(1 + \text{próby})}{\log(1 + \max\text{prób})}$ — premia za wyroby dobrze udokumentowane w MES.

Uruchamiany, gdy zapytanie nie ma BOM lub żaden kandydat go nie ma.

### 5.5. Kompozycja $S_{bom}$

$$S_{bom} = 0{,}70 \cdot S_{precyzja} + 0{,}30 \cdot S_{struktura}$$

**Precyzja** (obecność + zgodność ilości):
$$S_{precyzja} = 0{,}75 \cdot \text{Jaccard}(kody) + 0{,}25 \cdot \overline{sim_{ilość}}$$

gdzie $sim_{ilość}(q, c) = \frac{1}{1 + |q - c| / \max(q, c)}$.

**Struktura** (podobieństwo udziałów kategorii M01..M15):
$$S_{struktura} = \max\left(0,\ 1 - \frac{\text{L1}(udziały)}{2}\right)$$

### 5.6. Spłaszczanie BOM

Drzewo BOM (z półproduktami) jest rekurencyjnie spłaszczane do liści:
- mnożenie ilości przez ścieżkę drzewa,
- limit głębokości: **3 poziomy**,
- ochrona przed cyklem (visited set),
- półprodukt bez własnego BOM → „czarna skrzynka" (`is_semiproduct=True`),
- duplikaty `ptz_kod` w obrębie wyrobu: **sumowane**.

### 5.7. Semantyka braku BOM (wariant B)

**Spójna we wszystkich trybach:**

- **Brak BOM u zapytania** → składowa BOM pomijana, wagi renormalizowane.
- **Brak BOM u kandydata** (a zapytanie ma BOM) → kandydat dostaje **neutralne $S_{bom} = 0{,}5$**, wagi pozostają pełne.

**Uzasadnienie:** kandydat bez danych nie powinien być karany zerem (nie wiemy, czy jego BOM pasuje), ale też nie powinien wygrywać z kandydatem, który ma realny — choć słabo dopasowany — BOM.

### 5.8. Skalowanie krojenia

Tylko w trybie **DXF + kod**. Czas krojenia wzorca skalujemy stosunkiem długości cięcia:

$$t_{nowe} = t_{wzorzec} \cdot \frac{L_{nowe}}{L_{wzorzec}}$$

Percentyle (P25/P50/P75) skalują się razem z medianą.

### 5.9. Dlaczego mediana, nie średnia?

W produkcji plandek średnia arytmetyczna jest zaburzona przez:
- prototypy jednosztukowe (operator się uczy),
- pomyłki w rejestracji czasu,
- awarie maszyn i przerwy.

Mediana odrzuca outliery i wskazuje **realny, powtarzalny czas** seryjnego wykonania.

---

## 6. Rozwiązywanie Problemów

### Problem 1: Długość cięcia wynosi 0 m

**Przyczyna:** żadna warstwa w DXF nie jest rozpoznana jako cięcie.

**Rozwiązanie:**
1. Otwórz plik DXF w CAD i sprawdź nazwy warstw.
2. Dopisz je w sidebarze w polu **Warstwy cięcia** (oddzielone przecinkami).
3. Wróć do kalkulatora — cechy przeliczą się automatycznie.

### Problem 2: Zaburzone wymiary gabarytowe (np. 10× za duże)

**Przyczyna:** rysunek w innej skali niż domyślna 1:10.

**Rozwiązanie:** skala jest wpisana w `config.py` (`DRAWING_SCALE = 10.0`). Jeśli twoje rysunki są w innej skali — zgłoś się do działu IT. **W UI wszystkie wymiary są podawane jako rzeczywiste** (po korekcie ×10).

### Problem 3: Nowy kod klienta — brak w bazie

**Objaw:** komunikat „Nowy klient – dopasowanie po geometrii ⚠️".

**Rozwiązanie:** system automatycznie zeruje wagę klienta. Ranking działa po geometrii i BOM-ie. Aby dopasowanie po kliencie działało — musisz mieć historię tego klienta w MES.

### Problem 4: Baza danych jest nieaktualna

**Rozwiązanie:** sidebar → **📡 Pobierz MES z ERP** (tryb przyrostowy: 90 dni + rekordy niezamknięte). W razie problemów z połączeniem — **🔌 Testuj** i sprawdź poświadczenia w `.env`.

### Problem 5: Pobieranie BOM pomija część wyrobów

**Objaw:** w konsoli Streamlit komunikat „Pominięto N wierszy bez rozpoznanego rdzenia kodu".

**Przyczyna:** BOM obsługuje **wyłącznie kody `XXX-XXXX-XXX`** (np. `029-0421-018`). Kody tekstowe (`PROF-SHOPPEN 102260`, `PAKOWANIE VESTAS CHINA`, `!KOMPLET`) są pomijane — nie da się ich dopasować do kodu MES.

**Rozwiązanie:** to normalne. Jeśli chcesz mieć te wyroby w bazie, musisz je zaimportować do ERP z kodem w formacie `XXX-XXXX-XXX`.

### Problem 6: Wgranie DXF nie działa — „nazwa pliku nie przechodzi walidacji"

**Przyczyna:** plik nie zaczyna się od maski `AIxxx-xxxx-xxx`.

**Rozwiązanie:** zmień nazwę pliku, np. `plandeka.dxf` → `AI029-0421-013.dxf`. Sprawdź, że `AI` jest **wielkimi literami** — walidacja jest wrażliwa na wielkość liter.

### Problem 7: Kolumna Dział ZP pokazuje kreski

**Przyczyna:** nowe zlecenia w widoku ERP mogą mieć puste pole `DziałZP`.

**Rozwiązanie:** to normalne — starsze zlecenia mają to pole wypełnione, nowsze nie zawsze. Filtr Dział ZP w analizie ZP-ków obsługuje puste wartości.

### Problem 8: Finanse BOM są ukryte mimo poprawnego hasła

**Możliwe przyczyny:**
1. Hasło w `.env` nie jest ustawione (pole `BOM_FINANCE_PASSWORD`).
2. Wpisałeś hasło w polu, ale nie kliknąłeś **🔓 Odblokuj**.
3. Nacisnąłeś F5 po odblokowaniu (F5 kasuje `session_state`).

**Rozwiązanie:** wpisz hasło ponownie + kliknij Odblokuj. Jeśli nie pomaga — sprawdź z administratorem `.env`.

---

## 7. Dobre Praktyki Przygotowania Rysunków DXF

1. **Nazwa pliku:** `AIxxx-xxxx-xxx.dxf` (np. `AI029-0421-013.dxf`). Wymagane do wgrania do bazy.
2. **Warstwy:** używaj standardowych nazw (`CUT`, `OUTLINE`, `OBRYS`) lub dopisz swoje w sidebarze.
3. **Skala:** domyślnie 1:10. Rysunek w innej skali da błędne wymiary rzeczywiste (ale surowe mm do kalkulatora kroju są OK — te nie są korygowane).
4. **Model vs. layout:** rysunek w przestrzeni layoutu (nie „Model") — obsługiwany, ale podgląd 2D może nie działać poprawnie.
5. **Wielomateriałowość:** kilka plików o tym samym rdzeniu (np. `AI029-0421-013.dxf` i `AI029-0421-013_2.dxf`) — system **sumuje długości cięcia**.
6. **Eksport z CAD:** zapisuj jako `DXF R2018` lub `R2013`. Starsze formaty (R12) mogą nie zawierać wszystkich encji.

---

## 8. Najczęściej Zadawane Pytania (FAQ)

**P: Czy mogę wycenić wyrób bez pliku DXF?**
O: Tak — wybierz tryb **🔢 Tylko kod** i wpisz sam kod. Ranking użyje klienta + BOM (jeśli dostępne) albo klienta + daty + wiarygodności. Estymacja będzie mniej dokładna (brak skalowania krojenia).

**P: Ile próbek w MES jest potrzebnych, żeby estymacja była wiarygodna?**
O: Minimum 3–5 zakończonych operacji tego samego procesu na tym samym wyrobie. Poniżej tego mediana bywa niestabilna. System pokazuje liczbę prób w tabeli.

**P: Co jeśli wyrób ma 200 prób w MES, ale nowy wyrób ma zupełnie inną geometrię?**
O: W trybie DXF + kod skalowanie krojenia zrekompensuje różnicę długości cięcia. Pozostałe procesy — mediany wzorca wprost, bo nie mamy lepszej heurystyki.

**P: Dlaczego ranking pokazuje wyroby bez BOM-u?**
O: Od wersji 2.0 kandydaci bez BOM wchodzą do rankingu z neutralnym $S_{bom} = 0{,}5$. Nie są wykluczani — mogą wygrać, jeśli mają lepszą geometrię.

**P: Czy dane finansowe BOM są bezpieczne?**
O: W UI — tak, ukryte za hasłem. W bazie SQLite — **nie**, stawki są jawne. Ochrona dotyczy tylko warstwy prezentacji. Jeśli potrzeba szyfrowania danych w bazie — zgłoś do IT.

**P: Dlaczego po F5 tracę ustawienia wag?**
O: Streamlit przy F5 resetuje `session_state`. Defaulty z `config.py` są wtedy wczytywane na nowo. To zamierzone — nie musisz nic klikać, żeby wrócić do wartości domyślnych.

**P: Czy mogę dopisać własne kategorie materiałów?**
O: Tak, dopisując prefiksy w `bom_page.py` (słownik `CATEGORY_LABELS`). Wymaga edycji kodu — zgłoś do IT.

**P: Dlaczego BOM pomija wyrób o kodzie `PROF-SHOPPEN 102260`?**
O: BOM obsługuje wyłącznie kody `XXX-XXXX-XXX`. Kod tekstowy nie pasuje do żadnego wzorca i jest pomijany. To znane ograniczenie.

---

## 9. Historia zmian

### Wersja 2.0 (2026-10-13)
- **Silnik dopasowania:** dodana składowa BOM (3-składnikowa formuła), wagi 0,15 / 0,45 / 0,40.
- **Wariant B braku BOM:** kandydat bez BOM dostaje neutralne $S_{bom} = 0{,}5$ (spójne w trybach DXF + kod i kod + BOM).
- **Spłaszczanie BOM:** rekurencja z limitem głębokości (3), ochrona przed cyklem, sumowanie duplikatów.
- **Porównywarka Wyrobów:** grupa vs. jeden wyrób, percentyle, ostrzeżenie o rozrzucie geometrycznym, drill-down per wyrób.
- **Ochrona finansów BOM:** hasło w `.env`, odblokowanie w sidebarze, F5 kasuje.
- **Instrukcja:** pełna regeneracja — wszystkie rozdziały.

### Wersja 1.1 (poprzednia)
- Podstawowy estymator: DXF + MES (2-składnikowy).
- Kalkulator kroju (ZUND / LECTRA / JIGWEI).
- Baza MES z MES z ERP.
- Instrukcja niekompletna (urwana po rozdziale 2).
```

**Punktowe zmiany w `INSTRUKCJA_UZYTKOWNIKA.md`:**

- **Wersja:** 1.1 → 2.0.
- **Tytuł:** dodane „+ BOM".
- **Rozdział 1:** zachowany, doprecyzowany.
- **Rozdział 2:** dokończony (wersja 1.1 była urwana na mermaid graph).
- **Rozdział 3:** nowy — architektura, kody, warstwy, struktura katalogów.
- **Rozdział 4:** nowy — przewodnik po UI (sidebar, ekrany).
- **Rozdział 5:** nowy — matematyka: 3 tryby, wzory $S_{bom}$, wariant B, skalowanie.
- **Rozdział 6:** nowy — 8 typowych problemów z rozwiązaniami.
- **Rozdział 7:** nowy — dobre praktyki DXF.
- **Rozdział 8:** nowy — FAQ.
- **Rozdział 9:** nowy — historia zmian.

---

## 4. Checklista wdrożenia

1. **Zastąp** `src/ui/manual_page.py` nową wersją.
2. **Zastąp** `README.md` nową wersją.
3. **Zastąp** `INSTRUKCJA_UZYTKOWNIKA.md` nową wersją.
4. Zrestartuj Streamlit (Ctrl+C w terminalu, `python main.py --ui`).

---

## 5. Checklista testów

**a) Testy automatyczne:** — brak dedykowanych testów dla tych plików (dokumentacja), ale uruchom pełen zestaw dla pewności:

```bash
pytest -v
```

Oczekiwane: 67+ passed.

**b) Testy ręczne w UI:**

1. **Zakładka „🧠 Silnik dopasowania":**
   - Sekcja „Tryb 1: DXF + kod + BOM" — pokazuje asymetrię braku BOM (zapytanie vs. kandydat).
   - Sekcja „Tryb 2: Kod + BOM" — pokazuje, że kandydaci bez BOM wchodzą z 0,5.
   - **Brak** wzmianki o „pomijani kandydaci bez BOM".

2. **Zakładka „🧩 BOM i materiały":**
   - Sekcja „Kiedy BOM nie wchodzi do dopasowania" — dwa przypadki (nie trzy), z wartością `BOM_NEUTRAL_SIMILARITY = 0.5`.
   - Sekcja „Aktualizacja BOM z ERP" — ostrzeżenie o pomijaniu kodów bez formatu `XXX-XXXX-XXX`.
   - Sekcja „Ochrona danych finansowych" — obecna.

3. **Zakładka „🚀 Szybki start":**
   - Czwarta karta „🔒 Finanse BOM — odblokowanie hasłem" widoczna.

4. **Zakładka „📄 Pełny tekst":**
   - Wyświetla nową instrukcję 2.0 z pełnym spisem treści i wszystkimi 9 rozdziałami (nie urwaną po rozdz. 2).

5. **README.md:**
   - Otwórz w edytorze / podglądzie markdown.
   - Tytuł zawiera „+ BOM".
   - Sekcja „Tryby dopasowania" — tabela 3 trybów.
   - Sekcja „Zasady algorytmów" — pełna formuła 3-składnikowa + BOM.
   - Struktura projektu wymienia wszystkie pliki UI.

---

## 6. Ostrzeżenia

⚠️ **`manual_page.py` zawiera teraz sporo markdowna ze zmiennymi** (`BOM_NEUTRAL_SIMILARITY`, `WEIGHT_CLIENT`, `WEIGHT_GEOM`, `BOM_ALPHA_PRECYZJA`, `BOM_MAX_DEPTH`, `DRAWING_SCALE`). Jeśli zmienisz wartości w `config.py`, **teksty w instrukcji zaktualizują się automatycznie** — to celowe (single source of truth).

⚠️ **`INSTRUKCJA_UZYTKOWNIKA.md` jest teraz kompletnym dokumentem 2.0.** Poprzednia wersja 1.1 była urwana po rozdziale 2 — nie ma sensu jej odzyskiwać. Jeśli w repo istnieje gdzieś inna wersja (np. z dodatkowymi rozdziałami), trzeba ją ręcznie porównać i ewentualnie zmergować.

⚠️ **README nie zawiera już fragmentu „Szybki start" z CLI budowy bazy w starym formacie** — zaktualizowane o krok `cp .env.example .env` i sekcję konfiguracji. Upewnij się, że masz aktualny `.env.example` w repo.

✅ **Zero zmian w logice aplikacji** — poprawki dotyczą wyłącznie warstwy dokumentacji. Wszystkie istniejące testy powinny przejść bez zmian.

---

**Po wdrożeniu i przejściu testów mamy zamknięte wszystkie trzy poprawki dokumentacyjne. Jeśli chcesz kontynuować z drobiazgami kodu (nieużywane importy w `main.py` / `bom_page.py`, F5-caption w sidebarze, case-insensitive walidacja `AI`) — daj znać, to krótkie zmiany.** 🎯