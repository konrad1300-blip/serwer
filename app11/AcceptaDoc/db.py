# db.py
import sqlite3
import os
from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'acceptadoc.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA journal_mode = WAL')
    return g.db


def log_event(db, user_id, event_type, description,
              product_id=None, doc_version_id=None):
    db.execute(
        '''INSERT INTO audit_log (user_id, event_type, description, product_id, doc_version_id)
           VALUES (?,?,?,?,?)''',
        (user_id, event_type, description, product_id, doc_version_id)
    )


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_roles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role     TEXT NOT NULL,
    UNIQUE(user_id, role)
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT UNIQUE NOT NULL,
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS doc_versions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id        INTEGER NOT NULL REFERENCES products(id),
    version_num       INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    uploaded_by       INTEGER REFERENCES users(id),
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    is_current        INTEGER NOT NULL DEFAULT 1,
    UNIQUE(product_id, version_num)
);

CREATE TABLE IF NOT EXISTS approvals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_version_id    INTEGER NOT NULL REFERENCES doc_versions(id),
    stage             INTEGER NOT NULL,
    role              TEXT NOT NULL,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    decision          TEXT NOT NULL,
    checklist_json    TEXT NOT NULL,
    comment           TEXT,
    validity          TEXT NOT NULL DEFAULT 'WAZNA',
    on_behalf_of      TEXT,
    acted_by_user_id  INTEGER REFERENCES users(id),
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS correction_requests (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_version_id         INTEGER NOT NULL REFERENCES doc_versions(id),
    user_id                INTEGER NOT NULL REFERENCES users(id),
    role                   TEXT NOT NULL,
    failed_points_json     TEXT NOT NULL,
    description            TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'OTWARTE',
    resolved_by_version_id INTEGER REFERENCES doc_versions(id),
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at            TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(id),
    event_type     TEXT NOT NULL,
    description    TEXT NOT NULL,
    product_id     INTEGER REFERENCES products(id),
    doc_version_id INTEGER REFERENCES doc_versions(id),
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
'''


# ── STAŁE — single source of truth ─────────────────────────────────
STAGE1_ROLES = [
    'Konstruktor-Technolog',
    'Technolog',
    'Technolog-Wdrożeniowiec',
    'Lider Elementy',
    'Lider Szycie',
    'Lider Zgrzewanie T4',
    'Lider Zgrzewanie',
]
STAGE2_ROLES = ['QC', 'Administrator']

CHECKLISTS = {
    'Konstruktor-Technolog': [
        'TŁUMACZENIE',
        'RYSUNEK',
        'PLIKI DO KROJU',
        'SCHEMAT ŁĄCZENIA',
        'BOM W EXCEL',
        'LISTA ELEMENTÓW',
        'USTALENIE CZASÓW-EXCEL',
        'DOKUMENTACJA KROK PO KROKU',
        'ZDJĘCIA',
        'SPRAWDZENIE DOKUMENTACJI MOBIDOC',
        'AKCEPTACJA DOKUMENTACJI',
    ],
    'Technolog': [
        'TŁUMACZENIE',
        'RYSUNEK',
        'PLIKI DO KROJU',
        'SCHEMAT ŁĄCZENIA',
        'BOM W EXCEL',
        'LISTA ELEMENTÓW',
        'USTALENIE CZASÓW-EXCEL',
        'DOKUMENTACJA KROK PO KROKU',
        'ZDJĘCIA',
        'SPRAWDZENIE DOKUMENTACJI MOBIDOC',
        'AKCEPTACJA DOKUMENTACJI',
    ],
    'Technolog-Wdrożeniowiec': [
        'WYKONANIE PROTOTYPU',
        'USTALENIE KOLEJNOŚCI OPERACJI',
        'WERYFIKACJA CZASÓW',
        'WERYFIKACJA LISTY ELEMENTÓW',
        'WERYFIKACJA BOM',
    ],
    'Lider Elementy': [
        'Zapoznałem się z dokumentacją',
        'Dokumentacja pozwala wykonać moją część pracy',
        'Nie mam uwag wymagających poprawki',
    ],
    'Lider Szycie': [
        'Zapoznałem się z dokumentacją',
        'Dokumentacja pozwala wykonać moją część pracy',
        'Nie mam uwag wymagających poprawki',
    ],
    'Lider Zgrzewanie T4': [
        'Zapoznałem się z dokumentacją',
        'Dokumentacja pozwala wykonać moją część pracy',
        'Nie mam uwag wymagających poprawki',
    ],
    'Lider Zgrzewanie': [
        'Zapoznałem się z dokumentacją',
        'Dokumentacja pozwala wykonać moją część pracy',
        'Nie mam uwag wymagających poprawki',
    ],
    'QC': [
        'Pierwsza sztuka zgodna z dokumentacją',
        'Wymiary i tolerancje OK',
        'Materiały zgodne z BOM',
        'Brak uwag',
    ],
    'Administrator': [
        'Sprawdziłem, że wszyscy wymagani zaakceptowali Etap I',
        'Dokumentacja gotowa do zamknięcia',
    ],
}

SEED_USERS = [
    ('agata',      'Agata Englot',           ['Konstruktor-Technolog']),
    ('piotr_d',    'Piotr Dziubek',          ['Konstruktor-Technolog']),
    ('bartosz',    'Bartosz Piotrkowski',    ['Konstruktor-Technolog']),
    ('andrzej',    'Andrzej Krawczyk',       ['Konstruktor-Technolog']),
    ('kevin',      'Kevin Kalita',           ['Konstruktor-Technolog']),
    ('marlena',    'Marlena Pawłowska',      ['Technolog', 'Administrator']),
    ('katarzyna',  'Katarzyna Wojciechowska',['Technolog', 'Administrator']),
    ('konrad',     'Konrad Piaskowski',      ['Technolog', 'Administrator']),
    ('dorota_z',   'Dorota Zaręba',          ['Technolog-Wdrożeniowiec']),
    ('dorota_m',   'Dorota Markiewicz',      ['Technolog-Wdrożeniowiec']),
    ('blazej',     'Błażej Kieruj',          ['Technolog-Wdrożeniowiec']),
    ('marzena',    'Marzena Zielińska',      ['Lider Elementy']),
    ('marlena_k',  'Marlena Kuna',           ['Lider Szycie']),
    ('grazyna',    'Grażyna Muller',         ['Lider Zgrzewanie T4']),
    ('krzysztof',  'Krzysztof Dynia',        ['Lider Zgrzewanie']),
    ('joanna',     'Joanna Surma',           ['QC']),
    ('anna',       'Anna Krysztofińska',     ['QC']),
]


def _column_names(conn, table):
    return {row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _migrate_approvals(conn):
    """
    Idempotentna migracja tabeli approvals:
    dodaje on_behalf_of + acted_by_user_id jeśli ich nie ma.
    Bezpieczna dla istniejących baz — kolumny NULL dla starych rekordów.
    """
    cols = _column_names(conn, 'approvals')
    if 'on_behalf_of' not in cols:
        conn.execute('ALTER TABLE approvals ADD COLUMN on_behalf_of TEXT')
    if 'acted_by_user_id' not in cols:
        conn.execute('ALTER TABLE approvals ADD COLUMN acted_by_user_id INTEGER REFERENCES users(id)')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Migracje (idempotentne) — dla baz sprzed dodania kolumn.
    _migrate_approvals(conn)

    existing = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if existing == 0:
        from werkzeug.security import generate_password_hash
        pw_hash = generate_password_hash('111111')
        for username, full_name, roles in SEED_USERS:
            uid = conn.execute(
                'INSERT INTO users (username, full_name, password_hash) VALUES (?,?,?)',
                (username, full_name, pw_hash)
            ).lastrowid
            for role in roles:
                conn.execute(
                    'INSERT INTO user_roles (user_id, role) VALUES (?,?)',
                    (uid, role)
                )
        conn.commit()
    conn.close()