# admin_routes.py
"""
Trasy administracyjne — rejestrowane przez register_admin_routes(app).

Dlaczego osobny plik: app.py ma już ~700 linii logiki. Admin to
zamknięty zestaw funkcji (user CRUD + log + usuwanie produktu),
który nie miesza się z przepływem akceptacji.

Dlaczego bez blueprinta: endpointy muszą nazywać się `admin_users`,
`admin_log` itd. (a nie `admin.admin_users`) — inaczej trzeba by
poprawiać wszystkie url_for() w szablonach. Dlatego rejestrujemy
funkcją, nie przez Blueprint.
"""
import os
import shutil
import traceback
from datetime import datetime, timezone
from functools import wraps

from flask import (session, flash, redirect, url_for, request,
                   render_template, abort)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from db import get_db, log_event


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'documents')

ALL_ROLES = [
    'Konstruktor-Technolog',
    'Technolog',
    'Technolog-Wdrożeniowiec',
    'Lider Elementy',
    'Lider Szycie',
    'Lider Zgrzewanie T4',
    'Lider Zgrzewanie',
    'QC',
    'Administrator',
]


def _utc_now_str():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if 'Administrator' not in session.get('roles', []):
            flash('Brak uprawnień administratora.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def _user_has_history(db, user_id):
    """
    Sprawdza, czy user ma jakiekolwiek powiązane rekordy.
    Jeśli tak — trzeba anonimizować, nie twardo kasować.
    """
    checks = [
        ('approvals', 'user_id'),
        ('doc_versions', 'uploaded_by'),
        ('products', 'created_by'),
        ('correction_requests', 'user_id'),
        ('audit_log', 'user_id'),
    ]
    for table, column in checks:
        n = db.execute(
            f'SELECT COUNT(*) FROM {table} WHERE {column}=?', (user_id,)
        ).fetchone()[0]
        if n > 0:
            return True
    return False


def register_admin_routes(app):

    # ── Lista użytkowników ─────────────────────────────────────
    @app.route('/admin/users')
    @admin_required
    def admin_users():
        db = get_db()
        rows = db.execute('SELECT * FROM users ORDER BY full_name').fetchall()
        users = []
        for u in rows:
            roles = [r['role'] for r in db.execute(
                'SELECT role FROM user_roles WHERE user_id=?', (u['id'],)
            ).fetchall()]
            users.append({**dict(u), 'roles': roles})
        return render_template('admin_users.html', users=users)

    # ── Nowy użytkownik ────────────────────────────────────────
    @app.route('/admin/users/new', methods=['GET', 'POST'])
    @admin_required
    def admin_user_new():
        if request.method == 'POST':
            username = request.form['username'].strip()
            full_name = request.form['full_name'].strip()
            password = request.form['password']
            roles = request.form.getlist('roles')

            if not username or not full_name:
                flash('Nazwa użytkownika i imię są wymagane.', 'danger')
                return render_template('admin_user_form.html', all_roles=ALL_ROLES)
            if len(password) < 6:
                flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
                return render_template('admin_user_form.html', all_roles=ALL_ROLES)
            if not roles:
                flash('Wybierz co najmniej jedną rolę.', 'danger')
                return render_template('admin_user_form.html', all_roles=ALL_ROLES)
            invalid = [r for r in roles if r not in ALL_ROLES]
            if invalid:
                flash('Nieprawidłowa rola.', 'danger')
                return render_template('admin_user_form.html', all_roles=ALL_ROLES)

            db = get_db()
            if db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
                flash('Nazwa użytkownika już istnieje.', 'danger')
                return render_template('admin_user_form.html', all_roles=ALL_ROLES)

            uid = db.execute(
                'INSERT INTO users (username, full_name, password_hash) VALUES (?,?,?)',
                (username, full_name, generate_password_hash(password))
            ).lastrowid
            for role in roles:
                db.execute('INSERT INTO user_roles (user_id, role) VALUES (?,?)', (uid, role))
            log_event(db, session['user_id'], 'USER_UTWORZONY',
                      f'Utworzono użytkownika {username} ({full_name})')
            db.commit()
            flash(f'Użytkownik {username} utworzony.', 'success')
            return redirect(url_for('admin_users'))

        return render_template('admin_user_form.html', all_roles=ALL_ROLES)

    # ── Aktywacja/dezaktywacja ─────────────────────────────────
    @app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
    @admin_required
    def admin_user_toggle(user_id):
        db = get_db()
        u = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not u:
            abort(404)
        new_status = 0 if u['is_active'] else 1
        db.execute('UPDATE users SET is_active=? WHERE id=?', (new_status, user_id))
        log_event(db, session['user_id'], 'USER_STATUS',
                  f'{"Aktywowano" if new_status else "Dezaktywowano"} {u["username"]}')
        db.commit()
        flash('Status zmieniony.', 'success')
        return redirect(url_for('admin_users'))

    # ── Reset hasła ────────────────────────────────────────────
    @app.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
    @admin_required
    def admin_reset_password(user_id):
        new_pw = request.form.get('new_password', '').strip()
        if len(new_pw) < 6:
            flash('Hasło musi mieć co najmniej 6 znaków.', 'danger')
            return redirect(url_for('admin_users'))
        db = get_db()
        u = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not u:
            abort(404)
        db.execute('UPDATE users SET password_hash=? WHERE id=?',
                   (generate_password_hash(new_pw), user_id))
        log_event(db, session['user_id'], 'HASLO_RESET',
                  f'Zresetowano hasło {u["username"]}')
        db.commit()
        flash(f'Hasło {u["username"]} zmienione.', 'success')
        return redirect(url_for('admin_users'))

    # ── Usunięcie użytkownika (anonimizacja lub twarde) ────────
    @app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def admin_user_delete(user_id):
        if user_id == session['user_id']:
            flash('Nie możesz usunąć własnego konta.', 'danger')
            return redirect(url_for('admin_users'))

        db = get_db()
        u = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not u:
            abort(404)

        confirm = request.form.get('confirm_username', '').strip()
        if confirm != u['username']:
            flash('Nazwa użytkownika nie zgadza się z potwierdzeniem.', 'danger')
            return redirect(url_for('admin_users'))

        roles = [r['role'] for r in db.execute(
            'SELECT role FROM user_roles WHERE user_id=?', (user_id,)
        ).fetchall()]
        if 'Administrator' in roles and u['is_active']:
            active_admins = db.execute(
                '''SELECT COUNT(DISTINCT ur.user_id) FROM user_roles ur
                   JOIN users u ON u.id=ur.user_id
                   WHERE ur.role="Administrator" AND u.is_active=1'''
            ).fetchone()[0]
            if active_admins <= 1:
                flash('Nie można usunąć ostatniego aktywnego administratora.', 'danger')
                return redirect(url_for('admin_users'))

        if _user_has_history(db, user_id):
            anon_username = f'deleted_{user_id}'
            if db.execute('SELECT id FROM users WHERE username=?', (anon_username,)).fetchone():
                anon_username = f'deleted_{user_id}_{int(datetime.now(timezone.utc).timestamp())}'
            db.execute(
                '''UPDATE users SET username=?, full_name=?, is_active=0, password_hash="!"
                   WHERE id=?''',
                (anon_username, '[użytkownik usunięty]', user_id)
            )
            db.execute('DELETE FROM user_roles WHERE user_id=?', (user_id,))
            log_event(db, session['user_id'], 'USER_ZANONIMIZOWANY',
                      f'Zanonimizowano konto {u["username"]} ({u["full_name"]})')
            db.commit()
            flash(f'Konto {u["username"]} zanonimizowane (historia zachowana).', 'success')
        else:
            db.execute('DELETE FROM user_roles WHERE user_id=?', (user_id,))
            db.execute('DELETE FROM users WHERE id=?', (user_id,))
            log_event(db, session['user_id'], 'USER_USUNIETY',
                      f'Trwale usunięto konto {u["username"]} ({u["full_name"]})')
            db.commit()
            flash(f'Konto {u["username"]} usunięte.', 'success')

        return redirect(url_for('admin_users'))

    # ── Dziennik zdarzeń ───────────────────────────────────────
    @app.route('/admin/log')
    @admin_required
    def admin_log():
        db = get_db()
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 50
        offset = (page - 1) * per_page

        rows = db.execute(
            '''SELECT al.*, u.full_name FROM audit_log al
               LEFT JOIN users u ON u.id=al.user_id
               ORDER BY al.created_at DESC LIMIT ? OFFSET ?''',
            (per_page, offset)
        ).fetchall()
        total = db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
        return render_template('admin_log.html', logs=rows,
                               page=page, per_page=per_page, total=total)

    # ── Usuwanie produktu ──────────────────────────────────────
    @app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
    @admin_required
    def admin_product_delete(product_id):
        db = get_db()
        product = db.execute(
            'SELECT * FROM products WHERE id=? AND is_deleted=0', (product_id,)
        ).fetchone()
        if not product:
            abort(404)

        confirm = request.form.get('confirm_name', '').strip()
        if confirm != product['name']:
            flash('Nazwa potwierdzenia nie zgadza się.', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))

        try:
            dv_ids = [r['id'] for r in db.execute(
                'SELECT id FROM doc_versions WHERE product_id=?', (product_id,)
            ).fetchall()]

            if dv_ids:
                ph = ','.join('?' * len(dv_ids))

                # 1. Zdejmij FK audit_log.doc_version_id → doc_versions(id).
                #    Bez tego DELETE doc_versions zostaje zablokowany przez FK,
                #    bo każdy wpis historii (akceptacja, raport, nowa wersja)
                #    wskazuje na doc_version_id.
                db.execute(
                    f'UPDATE audit_log SET doc_version_id=NULL WHERE doc_version_id IN ({ph})',
                    dv_ids
                )

                # 2. Zdejmij FK correction_requests.resolved_by_version_id → doc_versions(id).
                #    Defensywnie: zgłoszenie z innej wersji mogło wskazywać
                #    na usuwaną wersję jako „rozwiązującą".
                db.execute(
                    f'UPDATE correction_requests SET resolved_by_version_id=NULL '
                    f'WHERE resolved_by_version_id IN ({ph})',
                    dv_ids
                )

                # 3. Usuń zależności bezpośrednie.
                db.execute(f'DELETE FROM approvals WHERE doc_version_id IN ({ph})', dv_ids)
                db.execute(f'DELETE FROM correction_requests WHERE doc_version_id IN ({ph})', dv_ids)

                # 4. Teraz doc_versions można bezpiecznie usunąć — żaden FK już nie blokuje.
                db.execute(f'DELETE FROM doc_versions WHERE id IN ({ph})', dv_ids)

            # 5. Zerwij powiązanie audit_log z produktem (product_id).
            db.execute(
                'UPDATE audit_log SET product_id=NULL WHERE product_id=?',
                (product_id,)
            )

            # 6. Usuń produkt.
            db.execute('DELETE FROM products WHERE id=?', (product_id,))
            log_event(db, session['user_id'], 'PRODUKT_USUNIETY',
                      f'Trwale usunięto produkt {product["name"]}')
            db.commit()
        except Exception as e:
            db.rollback()
            # Pełny traceback w terminalu — bez tego diagnoza jest zgadywaniem.
            traceback.print_exc()
            flash(f'Błąd podczas usuwania: {type(e).__name__}: {e}', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))

        product_dir = os.path.join(DATA_DIR, secure_filename(product['name']))
        if os.path.isdir(product_dir):
            try:
                shutil.rmtree(product_dir)
            except OSError as e:
                flash(f'Produkt usunięty, ale nie usunięto plików: {e}', 'warning')

        flash(f'Produkt {product["name"]} usunięty.', 'success')
        return redirect(url_for('products'))