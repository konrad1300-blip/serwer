#!/usr/bin/env python3
# cleanup_orphans.py
"""
Jednorazowy skrypt sprzątający sieroty w bazie AcceptaDoc.

Sierota = rekord wskazujący przez FK na nieistniejący wiersz
(np. `approvals.doc_version_id` wskazuje na nieistniejącą wersję
po nieudanym wcześniej `DELETE`).

Uruchomienie:
    python cleanup_orphans.py            # interaktywnie: raport + potwierdzenie
    python cleanup_orphans.py --dry-run  # tylko raport, zero zmian
    python cleanup_orphans.py --yes      # bez pytania (dla skryptów CI)

Bezpieczeństwo:
  - Przed zmianami robi kopię .backup (spójna kopia online, bezpieczna przy WAL).
  - Wszystko w jednej transakcji — błąd → rollback, baza wraca do stanu przed.
  - Jeśli baza czysta → kończy bez zmian.

Czego NIE robi:
  - Nie dotyka `users`, `user_roles`, `products`, `doc_versions` (nie usuwa
    prawdziwych danych — tylko sieroty z tabel zależnych).
  - Nie zmienia schematu.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'acceptadoc.db')


# (nazwa, opis, SQL liczący, SQL naprawczy)
CHECKS = [
    (
        'approvals → doc_versions',
        'Akceptacje wskazujące na nieistniejącą wersję dokumentacji',
        'SELECT COUNT(*) FROM approvals '
        'WHERE doc_version_id NOT IN (SELECT id FROM doc_versions)',
        'DELETE FROM approvals '
        'WHERE doc_version_id NOT IN (SELECT id FROM doc_versions)',
    ),
    (
        'correction_requests → doc_versions',
        'Zgłoszenia poprawek wskazujące na nieistniejącą wersję',
        'SELECT COUNT(*) FROM correction_requests '
        'WHERE doc_version_id NOT IN (SELECT id FROM doc_versions)',
        'DELETE FROM correction_requests '
        'WHERE doc_version_id NOT IN (SELECT id FROM doc_versions)',
    ),
    (
        'correction_requests.resolved_by_version_id → doc_versions',
        'Zgłoszenia z resolved_by_version_id wskazującym na nieistniejącą wersję',
        'SELECT COUNT(*) FROM correction_requests '
        'WHERE resolved_by_version_id IS NOT NULL '
        '  AND resolved_by_version_id NOT IN (SELECT id FROM doc_versions)',
        'UPDATE correction_requests SET resolved_by_version_id=NULL '
        'WHERE resolved_by_version_id IS NOT NULL '
        '  AND resolved_by_version_id NOT IN (SELECT id FROM doc_versions)',
    ),
    (
        'audit_log.doc_version_id → doc_versions',
        'Wpisy dziennika wskazujące na nieistniejącą wersję',
        'SELECT COUNT(*) FROM audit_log '
        'WHERE doc_version_id IS NOT NULL '
        '  AND doc_version_id NOT IN (SELECT id FROM doc_versions)',
        'UPDATE audit_log SET doc_version_id=NULL '
        'WHERE doc_version_id IS NOT NULL '
        '  AND doc_version_id NOT IN (SELECT id FROM doc_versions)',
    ),
    (
        'audit_log.product_id → products',
        'Wpisy dziennika wskazujące na nieistniejący produkt',
        'SELECT COUNT(*) FROM audit_log '
        'WHERE product_id IS NOT NULL '
        '  AND product_id NOT IN (SELECT id FROM products)',
        'UPDATE audit_log SET product_id=NULL '
        'WHERE product_id IS NOT NULL '
        '  AND product_id NOT IN (SELECT id FROM products)',
    ),
]


def _backup(conn, db_path):
    """Spójna kopia online — bezpieczna przy WAL i działającej aplikacji."""
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = f'{db_path}.bak-{ts}'
    backup_conn = sqlite3.connect(backup_path)
    try:
        conn.backup(backup_conn)
    finally:
        backup_conn.close()
    return backup_path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Tylko raport, bez zmian.')
    parser.add_argument('--yes', action='store_true',
                        help='Bez pytania o potwierdzenie (dla CI).')
    args = parser.parse_args()

    if not os.path.isfile(DB_PATH):
        print(f'❌ Nie znaleziono bazy: {DB_PATH}')
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    print(f'📂 Baza: {DB_PATH}')
    print(f'📊 Tryb: {"DRY-RUN (bez zmian)" if args.dry_run else "naprawa"}')
    print()

    total = 0
    results = []
    for name, desc, count_sql, fix_sql in CHECKS:
        n = conn.execute(count_sql).fetchone()[0]
        results.append((name, fix_sql, n))
        if n:
            print(f'  ⚠️  {name}: {n}  — {desc}')
            total += n

    if total == 0:
        print('✅ Baza czysta — brak sierot. Nic do zrobienia.')
        conn.close()
        return

    print()
    print(f'📊 Razem sierot: {total}')

    if args.dry_run:
        print('🔍 DRY-RUN — kończę bez zmian.')
        conn.close()
        return

    if not args.yes:
        ans = input('\n⚠️  Naprawić? Zostanie wykonana kopia zapasowa. [t/N] ').strip().lower()
        if ans != 't':
            print('Anulowano.')
            conn.close()
            return

    print('\n💾 Kopia zapasowa…')
    backup_path = _backup(conn, DB_PATH)
    print(f'   ✓ {backup_path}')

    print('\n🔧 Naprawiam…')
    try:
        for name, fix_sql, _ in results:
            cur = conn.execute(fix_sql)
            if cur.rowcount:
                print(f'   ✓ {name}: {cur.rowcount} rekordów')
        conn.commit()
        print('\n✅ Gotowe.')
    except Exception as e:
        conn.rollback()
        print(f'\n❌ Błąd: {e}')
        print('   Rollback — baza przywrócona do stanu przed zmianami.')
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()