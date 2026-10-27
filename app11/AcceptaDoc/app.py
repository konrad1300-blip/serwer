# app.py
import os
import io
import json
import time
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, send_file, jsonify, abort, g)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from db import (get_db, init_db, log_event,
                STAGE1_ROLES, STAGE2_ROLES, CHECKLISTS)
import pdf_report
import helps
from admin_routes import register_admin_routes


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'documents')

app = Flask(__name__)
app.secret_key = os.environ.get('ACCEPTADOC_SECRET') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

register_admin_routes(app)


# ── Helpers ──────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _utc_now_str():
    return _now().strftime('%Y-%m-%d %H:%M:%S')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user_roles = session.get('roles', [])
            if not any(r in user_roles for r in roles):
                flash('Brak uprawnień.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def _user_roles(db, user_id):
    return [r['role'] for r in db.execute(
        'SELECT role FROM user_roles WHERE user_id=?', (user_id,)
    ).fetchall()]


def _is_admin():
    return 'Administrator' in session.get('roles', [])


def _load_user_session(db, user):
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['roles'] = _user_roles(db, user['id'])
    session.permanent = True


def _safe_unique_name(db, base_name):
    candidate = base_name
    while db.execute('SELECT id FROM products WHERE name=?', (candidate,)).fetchone():
        candidate += '1'
    return candidate


def _product_status(db, product_id, doc_version_id):
    open_corr = db.execute(
        'SELECT id FROM correction_requests WHERE doc_version_id=? AND status="OTWARTE"',
        (doc_version_id,)
    ).fetchone()
    if open_corr:
        return 'WYMAGA POPRAWY'

    stage1_ok = {a['role'] for a in db.execute(
        'SELECT role FROM approvals WHERE doc_version_id=? AND stage=1 '
        'AND validity="WAZNA" AND decision="AKCEPTUJE"', (doc_version_id,)
    ).fetchall()}
    if not all(r in stage1_ok for r in STAGE1_ROLES):
        return 'ETAP I'

    stage2_ok = {a['role'] for a in db.execute(
        'SELECT role FROM approvals WHERE doc_version_id=? AND stage=2 '
        'AND validity="WAZNA" AND decision="AKCEPTUJE"', (doc_version_id,)
    ).fetchall()}
    if not all(r in stage2_ok for r in STAGE2_ROLES):
        return 'ETAP II'

    return 'ZAAKCEPTOWANY'


def _current_version(db, product_id):
    return db.execute(
        'SELECT * FROM doc_versions WHERE product_id=? AND is_current=1 '
        'ORDER BY version_num DESC LIMIT 1', (product_id,)
    ).fetchone()


def _stage_for_role(role):
    if role in STAGE1_ROLES:
        return 1
    if role in STAGE2_ROLES:
        return 2
    return None


def _role_already_taken(db, dv_id, role):
    return db.execute(
        'SELECT id FROM approvals WHERE doc_version_id=? AND role=? AND validity="WAZNA"',
        (dv_id, role)
    ).fetchone() is not None


def _stage_pool(status):
    """Pula ról dla bieżącego etapu (do walidacji 'za kogo')."""
    if status == 'ETAP I':
        return STAGE1_ROLES
    if status == 'ETAP II':
        return STAGE2_ROLES
    return []


def _admin_available_roles(db, dv_id, status):
    """
    Role, za które Administrator może zaakceptować (oprócz własnej roli Administrator).
    Wyklucza 'Administrator' — bo to własna rola admina, obsługiwana osobno.
    """
    pool = [r for r in _stage_pool(status) if r != 'Administrator']
    return [r for r in pool if not _role_already_taken(db, dv_id, r)]


def _admin_own_role(db, dv_id, status):
    """
    Czy Administrator może zaakceptować w swojej własnej roli (Administrator)?
    Tylko w Etapie II i tylko gdy rola 'Administrator' jeszcze nie obsadzona.
    Zwraca 'Administrator' albo None.
    """
    if status != 'ETAP II':
        return None
    if 'Administrator' not in STAGE2_ROLES:
        return None
    if _role_already_taken(db, dv_id, 'Administrator'):
        return None
    return 'Administrator'


def _compute_my_tasks(db, user_roles):
    tasks = []
    rows = db.execute(
        '''SELECT p.id as product_id, p.name as product_name,
                  dv.id as dv_id, dv.version_num, dv.created_at
           FROM doc_versions dv
           JOIN products p ON p.id = dv.product_id
           WHERE dv.is_current=1 AND p.is_deleted=0
           ORDER BY dv.created_at DESC'''
    ).fetchall()

    is_admin = 'Administrator' in user_roles

    for r in rows:
        status = _product_status(db, r['product_id'], r['dv_id'])
        if status == 'WYMAGA POPRAWY':
            continue

        matched = None

        # Zwykłe role użytkownika (bez Administratora)
        for role in user_roles:
            if role == 'Administrator':
                continue
            s = _stage_for_role(role)
            if not s:
                continue
            if status == 'ETAP I' and s != 1:
                continue
            if status == 'ETAP II' and s != 2:
                continue
            if not _role_already_taken(db, r['dv_id'], role):
                matched = {'my_role': role, 'my_stage': s, 'as_admin_for': None,
                           'admin_own_role': False}
                break

        # Administrator — własna rola Etapu II
        if not matched and is_admin:
            if _admin_own_role(db, r['dv_id'], status):
                matched = {'my_role': 'Administrator', 'my_stage': 2,
                           'as_admin_for': None, 'admin_own_role': True}

        # Administrator — za kogoś (dopiero gdy nie ma własnej roli)
        if not matched and is_admin:
            avail = _admin_available_roles(db, r['dv_id'], status)
            if avail:
                stage = 1 if status == 'ETAP I' else 2
                matched = {
                    'my_role': 'Administrator',
                    'my_stage': stage,
                    'as_admin_for': avail,
                    'admin_own_role': False,
                }

        if matched:
            tasks.append({**dict(r), **matched})

    return tasks


# ── Auto-logout (sliding) ────────────────────────────────────────
@app.before_request
def _check_session_timeout():
    if 'user_id' not in session:
        return
    last = session.get('last_seen')
    now = time.time()
    if last and (now - last) > 3600:
        session.clear()
        flash('Sesja wygasła po 1 godzinie bezczynności.', 'warning')
        return redirect(url_for('login'))
    session['last_seen'] = now


# ── Auth ────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username=? AND is_active=1', (username,)
        ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            _load_user_session(db, user)
            session['last_seen'] = time.time()
            log_event(db, user['id'], 'LOGIN', f'Zalogowano {username}')
            db.commit()
            return redirect(url_for('dashboard'))
        flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    if 'user_id' in session:
        db = get_db()
        log_event(db, session['user_id'], 'LOGOUT', f'Wylogowano {session["username"]}')
        db.commit()
    session.clear()
    return redirect(url_for('login'))


# ── Dashboard ───────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    db = get_db()
    user_roles = session.get('roles', [])

    my_tasks = _compute_my_tasks(db, user_roles)

    recent = db.execute(
        '''SELECT p.*, dv.version_num, dv.id as dv_id
           FROM products p
           LEFT JOIN doc_versions dv ON dv.product_id=p.id AND dv.is_current=1
           WHERE p.is_deleted=0
           ORDER BY p.created_at DESC LIMIT 10'''
    ).fetchall()

    products_with_status = []
    for p in recent:
        status = _product_status(db, p['id'], p['dv_id']) if p['dv_id'] else '—'
        products_with_status.append({**dict(p), 'status': status})

    total = db.execute('SELECT COUNT(*) FROM products WHERE is_deleted=0').fetchone()[0]
    stats = {'total': total, 'my_tasks': len(my_tasks)}

    return render_template('dashboard.html', my_tasks=my_tasks,
                           recent=products_with_status, stats=stats)


# ── Help ────────────────────────────────────────────────────────
@app.route('/help')
@login_required
def help_page():
    return render_template('help.html', sections=helps.HELP_SECTIONS)


# ── Products ────────────────────────────────────────────────────
@app.route('/products')
@login_required
def products():
    db = get_db()
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')

    rows = db.execute(
        '''SELECT p.*, dv.id as dv_id, dv.version_num
           FROM products p
           LEFT JOIN doc_versions dv ON dv.product_id=p.id AND dv.is_current=1
           WHERE p.is_deleted=0
           ORDER BY p.created_at DESC'''
    ).fetchall()

    items = []
    for r in rows:
        status = _product_status(db, r['id'], r['dv_id']) if r['dv_id'] else '—'
        if status_filter and status != status_filter:
            continue
        if q and q.lower() not in (r['name'] or '').lower():
            continue
        items.append({**dict(r), 'status': status})

    return render_template('products.html', items=items,
                           q=q, status_filter=status_filter)


@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def product_new():
    allowed = {'Konstruktor-Technolog', 'Technolog', 'Technolog-Wdrożeniowiec', 'Administrator'}
    if not any(r in session.get('roles', []) for r in allowed):
        flash('Tylko Konstruktor-Technolog, Technolog, Technolog-Wdrożeniowiec lub Administrator może tworzyć produkty.', 'danger')
        return redirect(url_for('products'))

    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename:
            flash('Musisz wgrać plik PDF z mobidoc. Utworzenie produktu bez pliku jest niemożliwe.', 'danger')
            return redirect(url_for('product_new'))

        if not f.filename.lower().endswith('.pdf'):
            flash('Dozwolone są tylko pliki PDF.', 'danger')
            return redirect(url_for('product_new'))

        base_name = f.filename[:-4]
        db = get_db()
        product_name = _safe_unique_name(db, base_name)

        client_dir = os.path.join(DATA_DIR, secure_filename(product_name))
        os.makedirs(client_dir, exist_ok=True)

        save_path = os.path.join(client_dir, f.filename)
        f.save(save_path)

        pid = db.execute(
            'INSERT INTO products (name, created_by) VALUES (?,?)',
            (product_name, session['user_id'])
        ).lastrowid

        did = db.execute(
            '''INSERT INTO doc_versions
               (product_id, version_num, original_filename, file_path, uploaded_by, is_current)
               VALUES (?,1,?,?,?,1)''',
            (pid, f.filename, save_path, session['user_id'])
        ).lastrowid

        log_event(db, session['user_id'], 'PRODUKT_UTWORZONY',
                  f'Utworzono produkt {product_name} z pliku {f.filename} (v001)',
                  product_id=pid, doc_version_id=did)
        db.commit()

        if product_name != base_name:
            flash(f'Produkt {product_name} utworzony (nazwa wystąpiła już w bazie — dodano sufiks).', 'warning')
        else:
            flash(f'Produkt {product_name} utworzony.', 'success')
        return redirect(url_for('product_detail', product_id=pid))

    return render_template('product_new.html')


@app.route('/products/<int:product_id>')
@login_required
def product_detail(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND is_deleted=0',
                         (product_id,)).fetchone()
    if not product:
        abort(404)

    current_dv = _current_version(db, product_id)
    versions = db.execute(
        'SELECT * FROM doc_versions WHERE product_id=? ORDER BY version_num DESC',
        (product_id,)
    ).fetchall()

    approvals = []
    corrections = []
    if current_dv:
        approvals = db.execute(
            '''SELECT a.*, u.full_name, au.full_name AS acted_by_name
               FROM approvals a
               JOIN users u ON u.id=a.user_id
               LEFT JOIN users au ON au.id=a.acted_by_user_id
               WHERE a.doc_version_id=? ORDER BY a.stage, a.created_at''',
            (current_dv['id'],)
        ).fetchall()
        corrections = db.execute(
            '''SELECT cr.*, u.full_name FROM correction_requests cr
               JOIN users u ON u.id=cr.user_id
               WHERE cr.doc_version_id=? ORDER BY cr.created_at DESC''',
            (current_dv['id'],)
        ).fetchall()

    history = db.execute(
        '''SELECT al.*, u.full_name FROM audit_log al
           LEFT JOIN users u ON u.id=al.user_id
           WHERE al.product_id=? ORDER BY al.created_at DESC LIMIT 100''',
        (product_id,)
    ).fetchall()

    status = _product_status(db, product_id, current_dv['id']) if current_dv else '—'

    # Zwykłe role użytkownika (bez Administratora)
    user_stage1_role = None
    if current_dv and status == 'ETAP I':
        for role in session.get('roles', []):
            if role == 'Administrator':
                continue
            if role in STAGE1_ROLES and not _role_already_taken(db, current_dv['id'], role):
                user_stage1_role = role
                break

    user_stage2_role = None
    if current_dv and status == 'ETAP II':
        for role in session.get('roles', []):
            if role == 'Administrator':
                continue
            if role in STAGE2_ROLES and not _role_already_taken(db, current_dv['id'], role):
                user_stage2_role = role
                break

    # Administrator: własna rola (Etap II) i/lub role „za kogoś"
    admin_own_role = None
    admin_available_roles = []
    if current_dv and _is_admin():
        admin_own_role = _admin_own_role(db, current_dv['id'], status)
        admin_available_roles = _admin_available_roles(db, current_dv['id'], status)

    can_upload = any(r in session.get('roles', []) for r in
                     {'Konstruktor-Technolog', 'Technolog', 'Technolog-Wdrożeniowiec', 'Administrator'})

    return render_template('product_detail.html',
                           product=product, current_dv=current_dv, versions=versions,
                           approvals=approvals, corrections=corrections, history=history,
                           status=status,
                           user_stage1_role=user_stage1_role,
                           user_stage2_role=user_stage2_role,
                           admin_own_role=admin_own_role,
                           admin_available_roles=admin_available_roles,
                           can_upload=can_upload,
                           STAGE1_ROLES=STAGE1_ROLES, STAGE2_ROLES=STAGE2_ROLES)


@app.route('/products/<int:product_id>/upload', methods=['POST'])
@login_required
def product_upload_version(product_id):
    allowed = {'Konstruktor-Technolog', 'Technolog', 'Technolog-Wdrożeniowiec', 'Administrator'}
    if not any(r in session.get('roles', []) for r in allowed):
        flash('Brak uprawnień do wymiany dokumentacji.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND is_deleted=0',
                         (product_id,)).fetchone()
    if not product:
        abort(404)

    current_dv = _current_version(db, product_id)
    if not current_dv:
        abort(404)

    f = request.files.get('file')
    if not f or not f.filename:
        flash('Nie wybrano pliku.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    if not f.filename.lower().endswith('.pdf'):
        flash('Dozwolone są tylko pliki PDF.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    approvals_count = db.execute(
        'SELECT COUNT(*) FROM approvals WHERE doc_version_id=? AND validity="WAZNA"',
        (current_dv['id'],)
    ).fetchone()[0]

    client_dir = os.path.join(DATA_DIR, secure_filename(product['name']))
    os.makedirs(client_dir, exist_ok=True)

    if approvals_count == 0:
        if os.path.isfile(current_dv['file_path']):
            try:
                os.remove(current_dv['file_path'])
            except OSError:
                pass
        new_path = os.path.join(client_dir, f.filename)
        f.save(new_path)
        db.execute(
            'UPDATE doc_versions SET original_filename=?, file_path=?, uploaded_by=?, created_at=? WHERE id=?',
            (f.filename, new_path, session['user_id'], _utc_now_str(), current_dv['id'])
        )
        log_event(db, session['user_id'], 'PLIK_PODMIENIONY',
                  f'Zastąpiono dokumentację v{current_dv["version_num"]:03d} plikiem {f.filename}',
                  product_id=product_id, doc_version_id=current_dv['id'])
        flash('Dokumentacja została zastąpiona (0 akceptacji).', 'success')
    else:
        new_num = current_dv['version_num'] + 1
        new_path = os.path.join(client_dir, f.filename)
        f.save(new_path)

        db.execute('UPDATE doc_versions SET is_current=0 WHERE product_id=?', (product_id,))
        db.execute('UPDATE approvals SET validity="UNIEWAZNIONA" WHERE doc_version_id=?',
                   (current_dv['id'],))

        did = db.execute(
            '''INSERT INTO doc_versions
               (product_id, version_num, original_filename, file_path, uploaded_by, is_current)
               VALUES (?,?,?,?,?,1)''',
            (product_id, new_num, f.filename, new_path, session['user_id'])
        ).lastrowid

        db.execute(
            '''UPDATE correction_requests
               SET status="POPRAWIONE", resolved_by_version_id=?, resolved_at=?
               WHERE doc_version_id=? AND status="OTWARTE"''',
            (did, _utc_now_str(), current_dv['id'])
        )

        log_event(db, session['user_id'], 'NOWA_WERSJA',
                  f'Utworzono v{new_num:03d} – poprzednie akceptacje unieważnione',
                  product_id=product_id, doc_version_id=did)
        flash(f'Utworzono nową wersję v{new_num:03d}. Poprzednie akceptacje unieważnione. Etap I zaczyna się od nowa.', 'warning')

    db.commit()
    return redirect(url_for('product_detail', product_id=product_id))


# ── Approval / correction ───────────────────────────────────────
@app.route('/products/<int:product_id>/approve/<int:dv_id>', methods=['GET', 'POST'])
@login_required
def approve(product_id, dv_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND is_deleted=0',
                         (product_id,)).fetchone()
    dv = db.execute('SELECT * FROM doc_versions WHERE id=? AND product_id=? AND is_current=1',
                    (dv_id, product_id)).fetchone()
    if not product or not dv:
        abort(404)

    status = _product_status(db, product_id, dv_id)
    if status == 'WYMAGA POPRAWY':
        flash('Ta wersja ma otwarte zgłoszenie poprawki. Poczekaj na nową wersję dokumentacji.', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
    if status == 'ZAAKCEPTOWANY':
        flash('Ta wersja została już w pełni zaakceptowana.', 'info')
        return redirect(url_for('product_detail', product_id=product_id))

    is_admin = _is_admin()
    requested_role = (request.args.get('role') or request.form.get('role_target') or '').strip()

    user_role = None
    stage = None
    as_admin_for = None

    if is_admin:
        own = _admin_own_role(db, dv_id, status)        # 'Administrator' albo None
        avail = _admin_available_roles(db, dv_id, status)

        if requested_role == 'Administrator':
            # Admin jawnie wybrał własną rolę — tylko jeśli wolna (Etap II)
            if own:
                user_role = 'Administrator'
                stage = 2
            else:
                flash('Rola Administrator jest już obsadzona w tej wersji.', 'info')
                return redirect(url_for('product_detail', product_id=product_id))

        elif requested_role and requested_role in avail:
            # Admin wybrał konkretną rolę „za kogoś" — tylko jeśli wolna
            user_role = requested_role
            stage = _stage_for_role(requested_role)
            as_admin_for = requested_role

        elif requested_role:
            # Wybrano rolę, której nie ma w puli lub jest obsadzona
            flash('Ta rola jest już obsadzona lub nie należy do bieżącego etapu.', 'danger')
            return redirect(url_for('product_detail', product_id=product_id))

        else:
            # Brak wyboru w URL/POST — decyduj automatycznie:
            # 1) jeśli admin ma własną rolę (Etap II) → wejdź od razu w checklistę Administratora
            # 2) w przeciwnym razie pokaż dropdown „za kogoś"
            if own:
                user_role = 'Administrator'
                stage = 2
            elif avail:
                return render_template('approval_form.html',
                                       product=product, dv=dv,
                                       user_role='Administrator',
                                       stage=None,
                                       checklist=None,
                                       as_admin_for=None,
                                       admin_own_role=None,
                                       admin_available_roles=avail,
                                       status=status)
            else:
                flash('Brak ról do obsadzenia — wszystko już zaakceptowane.', 'info')
                return redirect(url_for('product_detail', product_id=product_id))

    else:
        # Zwykły użytkownik
        for r in session.get('roles', []):
            s = _stage_for_role(r)
            if not s:
                continue
            if status == 'ETAP I' and s != 1:
                continue
            if status == 'ETAP II' and s != 2:
                continue
            if not _role_already_taken(db, dv_id, r):
                user_role = r
                stage = s
                break

        if not user_role:
            flash('Twoja rola została już obsadzona w tej wersji przez innego przedstawiciela.', 'warning')
            return redirect(url_for('product_detail', product_id=product_id))

    checklist = CHECKLISTS[user_role]

    if request.method == 'POST':
        decision = request.form.get('decision')
        if decision not in ('AKCEPTUJE', 'WYMAGA_POPRAWY'):
            flash('Nieprawidłowa decyzja.', 'danger')
            redirect_kwargs = {'product_id': product_id, 'dv_id': dv_id}
            if as_admin_for:
                redirect_kwargs['role'] = as_admin_for
            return redirect(url_for('approve', **redirect_kwargs))

        comment = request.form.get('comment', '').strip()

        if decision == 'AKCEPTUJE':
            checked = request.form.getlist('check')
            if len(checked) != len(checklist):
                flash('Musisz odklikać wszystkie punkty checklisty.', 'danger')
                redirect_kwargs = {'product_id': product_id, 'dv_id': dv_id}
                if as_admin_for:
                    redirect_kwargs['role'] = as_admin_for
                return redirect(url_for('approve', **redirect_kwargs))

            # on_behalf_of: TYLKO gdy admin za kogoś (nie za siebie)
            on_behalf = as_admin_for  # None dla zwykłej akceptacji Administratora
            acted_by = session['user_id'] if on_behalf else None

            db.execute(
                '''INSERT INTO approvals
                   (doc_version_id, stage, role, user_id, decision, checklist_json,
                    comment, validity, on_behalf_of, acted_by_user_id)
                   VALUES (?,?,?,?,?,?,?,"WAZNA",?,?)''',
                (dv_id, stage, user_role, session['user_id'], 'AKCEPTUJE',
                 json.dumps(checklist, ensure_ascii=False), comment,
                 on_behalf, acted_by)
            )

            if on_behalf:
                desc = f'[ADMIN] {session["full_name"]} zaakceptował jako {user_role}: v{dv["version_num"]:03d}'
                flash(f'Zaakceptowano jako {user_role} (Administrator za: {user_role}).', 'success')
            else:
                desc = f'{user_role}: Akceptuję v{dv["version_num"]:03d}'
                flash('Zaakceptowano.', 'success')

            log_event(db, session['user_id'], 'AKCEPTACJA', desc,
                      product_id=product_id, doc_version_id=dv_id)
        else:
            failed = request.form.getlist('failed_point')
            description = request.form.get('description', '').strip()
            if not failed:
                flash('Zaznacz co najmniej jeden punkt wymagający poprawy.', 'danger')
                redirect_kwargs = {'product_id': product_id, 'dv_id': dv_id}
                if as_admin_for:
                    redirect_kwargs['role'] = as_admin_for
                return redirect(url_for('approve', **redirect_kwargs))
            if not description:
                flash('Opis poprawki jest wymagany.', 'danger')
                redirect_kwargs = {'product_id': product_id, 'dv_id': dv_id}
                if as_admin_for:
                    redirect_kwargs['role'] = as_admin_for
                return redirect(url_for('approve', **redirect_kwargs))

            on_behalf = as_admin_for
            acted_by = session['user_id'] if on_behalf else None

            db.execute(
                '''INSERT INTO approvals
                   (doc_version_id, stage, role, user_id, decision, checklist_json,
                    comment, validity, on_behalf_of, acted_by_user_id)
                   VALUES (?,?,?,?,?,?,?,"WAZNA",?,?)''',
                (dv_id, stage, user_role, session['user_id'], 'WYMAGA_POPRAWY',
                 json.dumps(failed, ensure_ascii=False), comment,
                 on_behalf, acted_by)
            )
            db.execute(
                '''INSERT INTO correction_requests
                   (doc_version_id, user_id, role, failed_points_json, description, status)
                   VALUES (?,?,?,?,?,"OTWARTE")''',
                (dv_id, session['user_id'], user_role,
                 json.dumps(failed, ensure_ascii=False), description)
            )

            if on_behalf:
                desc = f'[ADMIN] {session["full_name"]} zgłosił poprawkę jako {user_role}: v{dv["version_num"]:03d}'
            else:
                desc = f'{user_role}: Wymaga poprawy v{dv["version_num"]:03d}'
            log_event(db, session['user_id'], 'POPRAWKA', desc,
                      product_id=product_id, doc_version_id=dv_id)
            flash('Zgłoszono poprawkę.', 'warning')

        db.commit()
        return redirect(url_for('product_detail', product_id=product_id))

    # GET — pokaż formularz
    return render_template('approval_form.html',
                           product=product, dv=dv,
                           user_role=user_role, stage=stage,
                           checklist=checklist,
                           as_admin_for=as_admin_for,
                           admin_own_role=_admin_own_role(db, dv_id, status),
                           admin_available_roles=_admin_available_roles(db, dv_id, status),
                           status=status)


# ── PDF ─────────────────────────────────────────────────────────
@app.route('/products/<int:product_id>/report')
@login_required
def generate_report(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND is_deleted=0',
                         (product_id,)).fetchone()
    if not product:
        abort(404)

    dv = _current_version(db, product_id)
    if not dv:
        flash('Brak wersji dokumentacji.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    approvals = db.execute(
        '''SELECT a.*, u.full_name, au.full_name AS acted_by_name
           FROM approvals a
           JOIN users u ON u.id=a.user_id
           LEFT JOIN users au ON au.id=a.acted_by_user_id
           WHERE a.doc_version_id=? AND a.validity="WAZNA"
           ORDER BY a.stage, a.created_at''',
        (dv['id'],)
    ).fetchall()

    history = db.execute(
        '''SELECT al.*, u.full_name FROM audit_log al
           LEFT JOIN users u ON u.id=al.user_id
           WHERE al.product_id=? ORDER BY al.created_at ASC''',
        (product_id,)
    ).fetchall()

    pdf_bytes = pdf_report.generate(product, dv, approvals, history)
    log_event(db, session['user_id'], 'RAPORT',
              f'Wygenerowano kartę PDF dla v{dv["version_num"]:03d}',
              product_id=product_id, doc_version_id=dv['id'])
    db.commit()

    ts = _now().strftime('%Y%m%d%H%M%S')
    filename = f"{product['name']}_v{dv['version_num']:03d}_{ts}.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                     as_attachment=True, download_name=filename)


# ── Download pliku ──────────────────────────────────────────────
@app.route('/versions/<int:dv_id>/download')
@login_required
def download_version(dv_id):
    db = get_db()
    dv = db.execute('SELECT * FROM doc_versions WHERE id=?', (dv_id,)).fetchone()
    if not dv or not os.path.isfile(dv['file_path']):
        abort(404)
    return send_file(dv['file_path'], as_attachment=True,
                     download_name=dv['original_filename'])


# ── Profile ─────────────────────────────────────────────────────
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '').strip()
        if not check_password_hash(user['password_hash'], current_pw):
            flash('Nieprawidłowe aktualne hasło.', 'danger')
        elif len(new_pw) < 6:
            flash('Nowe hasło musi mieć co najmniej 6 znaków.', 'danger')
        else:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',
                       (generate_password_hash(new_pw), session['user_id']))
            log_event(db, session['user_id'], 'HASLO', 'Zmieniono własne hasło')
            db.commit()
            flash('Hasło zmienione.', 'success')
            user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()

    roles = _user_roles(db, session['user_id'])
    return render_template('profile.html', user=user, roles=roles)


# ── API ─────────────────────────────────────────────────────────
@app.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    db = get_db()
    rows = db.execute(
        'SELECT id, name FROM products WHERE is_deleted=0 AND name LIKE ? ORDER BY name LIMIT 10',
        (f'%{q}%',)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Init ────────────────────────────────────────────────────────
@app.teardown_appcontext
def _close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5011, debug=True)