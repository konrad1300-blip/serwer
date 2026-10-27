# helps.py
"""
Treść strony pomocy — pod nowy model (produkt = plik z mobidoc, bez rewizji).
Każda sekcja to dict: id, icon, title, blocks.
Block types: p, h3, ul, ol, example, note.
"""

HELP_SECTIONS = [

    {
        'id': 'czym-jest',
        'icon': '🎯',
        'title': 'Czym jest AcceptaDoc',
        'blocks': [
            {'type': 'p', 'text': (
                'AcceptaDoc to system do zarządzania i akceptacji dokumentacji '
                'technicznej produktów. Dokumentację pobierasz z dysku <strong>mobidoc</strong> '
                'i wgrywasz do systemu. Tu dokumentacja przechodzi proces akceptacji '
                '— od Konstruktora-Technologa, przez Technologów, Liderów produkcji, '
                'aż po QC i Administratora.'
            )},
            {'type': 'p', 'text': (
                'Dzięki systemowi zawsze wiadomo: kto, kiedy i którą wersję dokumentacji '
                'zatwierdził. Nic nie ginie w mailach, nikt nie pracuje na nieaktualnym pliku.'
            )},
        ],
    },

    {
        'id': 'role',
        'icon': '👥',
        'title': 'Role w systemie',
        'blocks': [
            {'type': 'p', 'text': 'W systemie mamy 9 ról:'},
            {'type': 'ul', 'items': [
                '<strong>Konstruktor-Technolog</strong> — osoba opracowująca dokumentację techniczną (rysunki, BOM, tłumaczenia, schematy).',
                '<strong>Technolog</strong> — osoba sprawdzająca dokumentację pod kątem gotowości produkcyjnej. Marlena Pawłowska, Katarzyna Wojciechowska, Konrad Piaskowski.',
                '<strong>Technolog-Wdrożeniowiec</strong> — osoba wdrażająca produkt: prototyp, kolejność operacji, czasy, lista elementów. Dorota Zaręba, Dorota Markiewicz, Błażej Kieruj.',
                '<strong>Lider Elementy</strong> — Marzena Zielińska.',
                '<strong>Lider Szycie</strong> — Marlena Kuna.',
                '<strong>Lider Zgrzewanie T4</strong> — Grażyna Muller.',
                '<strong>Lider Zgrzewanie</strong> — Krzysztof Dynia.',
                '<strong>QC (Kontrola Jakości)</strong> — Joanna Surma, Anna Krysztofińska. Sprawdzają pierwszą sztukę w Etapie II.',
                '<strong>Administrator</strong> — Marlena, Katarzyna, Konrad. Mają uprawnienia nadzorcze i administracyjne.',
            ]},
            {'type': 'note', 'text': (
                'Marlena Pawłowska, Katarzyna Wojciechowska i Konrad Piaskowski mają '
                '<strong>dwie role jednocześnie</strong>: Technolog i Administrator. '
                'W Etapie I akceptują jako Technolog, w Etapie II jako Administrator.'
            )},
        ],
    },

    {
        'id': 'proces',
        'icon': '📋',
        'title': 'Proces krok po kroku',
        'blocks': [
            {'type': 'ol', 'items': [
                '<strong>Utworzenie produktu.</strong> Konstruktor-Technolog, Technolog lub Administrator wgrywa plik PDF z mobidoc. Nazwa pliku staje się nazwą produktu (np. <code>001-1119-004_20261006_1046</code>).',
                '<strong>Etap I — akceptacje techniczne.</strong> Siedem ról musi zaakceptować dokumentację: Konstruktor-Technolog, Technolog, Technolog-Wdrożeniowiec i czterej Liderzy. Każda rola to <strong>jeden przedstawiciel</strong> — pierwszy, który kliknie „Akceptuję", zamyka rolę. Reszta widzi „już obsadzone".',
                '<strong>Checklista.</strong> Przed kliknięciem „Akceptuję" musisz odklikać wszystkie punkty checklisty właściwej dla twojej roli. Bez tego przycisk jest nieaktywny.',
                '<strong>Zgłoszenie poprawki.</strong> Jeśli coś jest nie tak — kliknij „Wymaga poprawy", zaznacz punkty i opisz, co poprawić. Twórca widzi zgłoszenie i wgrywa nowy plik.',
                '<strong>Etap II — QC + Administrator.</strong> Gdy wszystkie 7 ról Etapu I zaakceptuje, dokumentacja trafia do QC i Administratora. Wystarczy 1 QC + 1 Administrator.',
                '<strong>Zaakceptowany.</strong> Po Etapie II produkt ma status „ZAAKCEPTOWANY". Można pobrać kartę PDF z pełną historią.',
            ]},
        ],
    },

    {
        'id': 'checklisty',
        'icon': '✅',
        'title': 'Checklisty per rola',
        'blocks': [
            {'type': 'p', 'text': 'Każda rola ma własną listę punktów do odklikania:'},
            {'type': 'ul', 'items': [
                '<strong>Konstruktor-Technolog i Technolog</strong> (11 pkt): Tłumaczenie, Rysunek, Pliki do kroju, Schemat łączenia, BOM w Excel, Lista elementów, Ustalenie czasów, Dokumentacja krok po kroku, Zdjęcia, Sprawdzenie dokumentacji mobidoc, Akceptacja dokumentacji.',
                '<strong>Technolog-Wdrożeniowiec</strong> (5 pkt): Wykonanie prototypu, Ustalenie kolejności operacji, Weryfikacja czasów, Weryfikacja listy elementów, Weryfikacja BOM.',
                '<strong>Liderzy produkcji</strong> (3 pkt): Zapoznałem się z dokumentacją, Dokumentacja pozwala wykonać moją część pracy, Nie mam uwag.',
                '<strong>QC</strong> (4 pkt): Pierwsza sztuka zgodna, Wymiary i tolerancje OK, Materiały zgodne z BOM, Brak uwag.',
                '<strong>Administrator</strong> (2 pkt): Sprawdziłem, że wszyscy wymagani zaakceptowali Etap I, Dokumentacja gotowa do zamknięcia.',
            ]},
        ],
    },

    {
        'id': 'wersje',
        'icon': '🔢',
        'title': 'Wymiana dokumentacji i nowe wersje',
        'blocks': [
            {'type': 'p', 'text': (
                'Dokumentację można wymienić na dwa sposoby — zależnie od tego, '
                'czy ktokolwiek już ją zaakceptował:'
            )},
            {'type': 'ul', 'items': [
                '<strong>Zero akceptacji</strong> — plik zostaje zastąpiony w tej samej wersji (v001 zostaje v001). Bez utraty historii.',
                '<strong>Co najmniej jedna akceptacja</strong> — tworzona jest nowa wersja (v001 → v002). Wszystkie dotychczasowe akceptacje zostają unieważnione, Etap I zaczyna się od nowa.',
            ]},
            {'type': 'example', 'text': (
                'Agata zaakceptowała v001. Konstruktor-Technolog widzi błąd, wgrywa nowy plik. '
                'System tworzy v002 i unieważnia akceptację Agaty. Agata musi zaakceptować v002.'
            )},
        ],
    },

    {
        'id': 'pdf',
        'icon': '📄',
        'title': 'Karta PDF',
        'blocks': [
            {'type': 'p', 'text': 'Z każdego produktu można wygenerować kartę PDF. Zawiera:'},
            {'type': 'ul', 'items': [
                'Nazwę produktu i wersję.',
                'Tabelę akceptacji Etapu I (7 wierszy — wszystkie role).',
                'Tabelę akceptacji Etapu II (2 wiersze — QC i Administrator).',
                'Podpisy imienne: „Zatwierdzone przez [Imię Nazwisko] (rola, etap, data)".',
                '<strong>Historię zdarzeń</strong> — wszystkie logi produktu (utworzenie, akceptacje, poprawki, nowe wersje, pobrania).',
            ]},
            {'type': 'p', 'text': 'Pobranie PDF jest logowane w historii produktu.'},
        ],
    },

    {
        'id': 'admin',
        'icon': '🛡️',
        'title': 'Administratorzy — co mogą',
        'blocks': [
            {'type': 'p', 'text': 'Trzej adminowie (Marlena, Katarzyna, Konrad) mają dodatkowe uprawnienia:'},
            {'type': 'ul', 'items': [
                'Tworzenie, dezaktywacja i reset haseł użytkowników.',
                'Usuwanie produktów (z potwierdzeniem nazwy).',
                'Usuwanie użytkowników — anonimizacja (jeśli mają historię) lub twarde usunięcie (jeśli nie mają).',
                'Wgląd w dziennik zdarzeń systemu.',
                'Akceptacja w Etapie II (1 z 3 wystarczy).',
            ]},
            {'type': 'h3', 'text': 'Akceptacja za dowolną rolę'},
            {'type': 'p', 'text': (
                'Administrator może zaakceptować dokumentację <strong>za dowolną rolę</strong>, '
                'która w danym etapie nie jest jeszcze obsadzona — np. za Lidera Szycie, QC, Technologa. '
                'Taka decyzja jest wyraźnie oznaczona w raporcie PDF i w dzienniku zdarzeń: '
                '„Administrator za: [rola]".'
            )},
            {'type': 'note', 'text': (
                'Administrator nie nadpisuje istniejących akceptacji. Jeśli rola jest już obsadzona, '
                'nie pojawia się na liście „akceptuj jako…". Aby zmienić decyzję, trzeba wgrać nową '
                'wersję dokumentacji (co i tak unieważnia wszystkie akceptacje).'
            )},
        ],
    },

    {
        'id': 'faq',
        'icon': '❓',
        'title': 'FAQ',
        'blocks': [
            {'type': 'h3', 'text': 'Dlaczego nie widzę zadania do akceptacji?'},
            {'type': 'p', 'text': (
                'Możliwe powody: (1) twoja rola została już obsadzona przez innego przedstawiciela; '
                '(2) dokumentacja jest w Etapie II, a twoja rola jest w Etapie I; '
                '(3) produkt ma otwarte zgłoszenie poprawki.'
            )},
            {'type': 'h3', 'text': 'Czy Administrator może zaakceptować za mnie?'},
            {'type': 'p', 'text': (
                'Tak — jeśli twoja rola jest jeszcze nieobsadzona, Administrator może zaakceptować w twoim '
                'imieniu. W raporcie i w logach będzie to oznaczone: „Administrator za: [twoja rola]". '
                'Jeśli już zaakceptowałeś, Administrator nie może tego nadpisać.'
            )},
            {'type': 'h3', 'text': 'Czy mogę cofnąć akceptację?'},
            {'type': 'p', 'text': (
                'Nie bezpośrednio. Akceptacja to decyzja formalna. Jeśli trzeba coś zmienić, '
                'twórca produktu wgrywa nowy plik → nowa wersja → akceptacje unieważnione.'
            )},
            {'type': 'h3', 'text': 'Jak zmienić hasło?'},
            {'type': 'p', 'text': 'Kliknij swoje imię → „Mój profil". Wpisz aktualne hasło i nowe.'},
            {'type': 'h3', 'text': 'Co się dzieje przy podmianie pliku?'},
            {'type': 'p', 'text': (
                'Jeśli 0 akceptacji — plik zastąpiony w tej samej wersji. '
                'Jeśli ≥1 akceptacja — nowa wersja, akceptacje unieważnione.'
            )},
            {'type': 'h3', 'text': 'Dlaczego sesja mnie wylogowuje?'},
            {'type': 'p', 'text': (
                'Po 1 godzinie bezczynności sesja wygasa automatycznie. '
                'Każde kliknięcie w systemie przesuwa ten zegar.'
            )},
        ],
    },

    {
        'id': 'pierwsze-kroki',
        'icon': '🚀',
        'title': 'Pierwsze kroki',
        'blocks': [
            {'type': 'ol', 'items': [
                '<strong>Zmień hasło.</strong> Kliknij imię → Mój profil. Hasło startowe to <code>111111</code>.',
                '<strong>Sprawdź „Moje zadania"</strong> na Panelu — tam pojawiają się produkty czekające na twoją akceptację.',
                '<strong>Otwórz zadanie</strong>, przeczytaj dokumentację, odklikaj checklistę i kliknij „Akceptuję" — albo „Wymaga poprawy", jeśli coś jest nie tak.',
                '<strong>W razie wątpliwości</strong> — zajrzyj do tej pomocy lub zapytaj twórcę produktu.',
            ]},
        ],
    },
]