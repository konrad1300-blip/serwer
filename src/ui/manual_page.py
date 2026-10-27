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