#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KIT-zen – system zarządzania projektami z priorytetami, trackingiem czasu,
widokiem Kanban, zaawansowanymi wykresami i optymalizacją zapytań.
"""

import os
from datetime import datetime, date, timedelta, timezone
from functools import wraps
import io
import base64

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField, BooleanField, TextAreaField, DateField, IntegerField
from wtforms.validators import InputRequired, Length, Optional, NumberRange
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from weasyprint import HTML
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from werkzeug.middleware.proxy_fix import ProxyFix

# ----------------------------- KONFIGURACJA -----------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['SECRET_KEY'] = 'klucz-do-zmiany-w-produkcji'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kitzen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Proszę się zalogować.'

# ----------------------------- FUNKCJE POMOCNICZE DLA CZASU -----------------------------
def now_aware():
    """Zwraca świadomy czas UTC (zamiast przestarzałego datetime.utcnow)."""
    return datetime.now(timezone.utc)

def ensure_aware(dt):
    """Konwertuje naiwny datetime na świadomy UTC; jeśli już świadomy, zwraca go jako UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# ----------------------------- MODELE BAZY DANYCH -----------------------------
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'))
)

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    absence_start = db.Column(db.Date, nullable=True)
    absence_end = db.Column(db.Date, nullable=True)
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))

    def has_role(self, role_name):
        return any(r.name == role_name for r in self.roles)

    def has_any_role(self, role_names):
        if isinstance(role_names, str):
            role_names = [r.strip() for r in role_names.split(',')]
        return any(self.has_role(r) for r in role_names)

class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now_aware)
    deadline = db.Column(db.Date, nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    steps = db.relationship('Step', backref='project', order_by='Step.position', cascade='all, delete-orphan')

class Step(db.Model):
    __tablename__ = 'step'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    position = db.Column(db.Integer, default=0)
    planned_hours = db.Column(db.Float, default=1.0)
    status = db.Column(db.String(20), default='todo')   # todo, in_progress, paused, done
    required_roles = db.Column(db.String(200), nullable=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    status_updated_at = db.Column(db.DateTime, default=now_aware, onupdate=now_aware)
    priority = db.Column(db.String(20), default='normalny')   # normalny, pilny, natychmiast
    started_at = db.Column(db.DateTime, nullable=True)        # zastąpione przez TimeLog, ale zostawiam dla kompatybilności
    actual_hours = db.Column(db.Float, nullable=True)         # obliczane z TimeLog
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id])

    def can_be_started(self):
        if not self.project:
            return False
        prev_steps = Step.query.filter(
            Step.project_id == self.project_id,
            Step.position < self.position,
            Step.status != 'done'
        ).first()
        return prev_steps is None

    def is_blocked(self):
        return not self.can_be_started()

class TimeLog(db.Model):
    __tablename__ = 'time_log'
    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey('step.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=now_aware)
    end_time = db.Column(db.DateTime, nullable=True)
    step = db.relationship('Step', backref='time_logs')
    user = db.relationship('User')

class LogEntry(db.Model):
    __tablename__ = 'log_entry'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=now_aware, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80))
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    user = db.relationship('User')

class ProductionCheck(db.Model):
    __tablename__ = 'production_check'
    pzl_id = db.Column(db.String(100), primary_key=True)
    prod_kod = db.Column(db.String(200), nullable=True)
    zp = db.Column(db.String(200), nullable=True)
    dizallzp = db.Column(db.String(200), nullable=True)
    data_aktywacji = db.Column(db.DateTime, nullable=True)
    row_number = db.Column(db.Integer, nullable=True)
    sprawdzono = db.Column(db.Boolean, default=False)
    checked_by = db.Column(db.String(80), nullable=True)
    checked_at = db.Column(db.DateTime, nullable=True)

# ----------------------------- MODELE SZABLONÓW -----------------------------
class ProjectTemplate(db.Model):
    __tablename__ = 'project_template'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    is_builtin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_aware)
    steps = db.relationship('StepTemplate', backref='template', cascade='all, delete-orphan', order_by='StepTemplate.position')

class StepTemplate(db.Model):
    __tablename__ = 'step_template'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    planned_hours = db.Column(db.Float, default=1.0)
    required_roles = db.Column(db.String(200), nullable=True)
    position = db.Column(db.Integer, default=0)
    template_id = db.Column(db.Integer, db.ForeignKey('project_template.id'), nullable=True)
    is_standalone = db.Column(db.Boolean, default=True)

# ----------------------------- FORMULARZE -----------------------------
class LoginForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[InputRequired()])
    password = PasswordField('Hasło', validators=[InputRequired()])

class UserForm(FlaskForm):
    username = StringField('Nazwa użytkownika', validators=[InputRequired(), Length(min=3, max=80)])
    password = PasswordField('Hasło', validators=[InputRequired(), Length(min=4)])
    is_admin = BooleanField('Administrator')
    roles = SelectField('Role (wybierz jedną)', choices=[('technolog','Technolog'),('konstruktor','Konstruktor'),('wdrożeniowiec','Wdrożeniowiec'),('QC','Kontrola jakości')], validators=[Optional()])
    absence_start = DateField('Początek nieobecności', validators=[Optional()])
    absence_end = DateField('Koniec nieobecności', validators=[Optional()])

class ProjectForm(FlaskForm):
    name = StringField('Nazwa projektu', validators=[InputRequired()])
    description = TextAreaField('Opis')
    deadline = DateField('Termin końcowy (opcjonalnie)', validators=[Optional()])
    template_choice = SelectField('Lub użyj szablonu', choices=[], validators=[Optional()])

class StepForm(FlaskForm):
    name = StringField('Nazwa kroku', validators=[InputRequired()])
    description = TextAreaField('Opis')
    planned_hours = FloatField('Planowany czas (godziny)', validators=[InputRequired(), NumberRange(min=0.1)])
    required_roles = StringField('Wymagane role (oddzielone przecinkami)', validators=[Optional()])
    assigned_user_id = SelectField('Przypisz do użytkownika', coerce=int, choices=[], validators=[Optional()])
    step_template_id = SelectField('Wybierz szablon kroku (wypełni poniższe pola)', choices=[], coerce=int, validators=[Optional()])
    priority = SelectField('Priorytet', choices=[
        ('normalny', 'Normalny'),
        ('pilny', 'Pilny'),
        ('natychmiast', 'Natychmiast')
    ], default='normalny', validators=[Optional()])

class ProjectTemplateForm(FlaskForm):
    name = StringField('Nazwa szablonu', validators=[InputRequired(), Length(max=100)])
    description = TextAreaField('Opis')

class StepTemplateForm(FlaskForm):
    name = StringField('Nazwa kroku', validators=[InputRequired()])
    description = TextAreaField('Opis')
    planned_hours = FloatField('Planowane godziny', validators=[InputRequired(), NumberRange(min=0.1)])
    required_roles = StringField('Wymagane role')

# ----------------------------- FUNKCJE LOGOWANIA -----------------------------
def log_action(action, details=None):
    username = current_user.username if current_user.is_authenticated else 'SYSTEM'
    user_id = current_user.id if current_user.is_authenticated else None
    entry = LogEntry(username=username, user_id=user_id, action=action, details=details)
    db.session.add(entry)
    db.session.commit()
    cutoff = now_aware() - timedelta(days=30)
    db.session.query(LogEntry).filter(LogEntry.timestamp < cutoff).delete()
    db.session.commit()

# ----------------------------- DEKORATORY -----------------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Dostęp tylko dla administratora.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role_names):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Proszę się zalogować.', 'warning')
                return redirect(url_for('login'))
            if current_user.is_admin:
                return f(*args, **kwargs)
            if not current_user.has_any_role(role_names):
                flash('Nie masz odpowiednich uprawnień.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ----------------------------- FUNKCJE WYKRESÓW -----------------------------
def generate_workload_chart():
    users = User.query.all()
    workloads = []
    user_names = []
    for u in users:
        steps_in_progress = Step.query.filter_by(assigned_user_id=u.id, status='in_progress').all()
        total_hours = sum(s.planned_hours for s in steps_in_progress)
        workloads.append(total_hours)
        user_names.append(u.username)
    plt.figure(figsize=(8,4))
    plt.bar(user_names, workloads, color='skyblue')
    plt.title('Obciążenie pracowników (godziny zadań w trakcie)')
    plt.ylabel('Godziny')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_tasks_per_role_chart():
    roles = ['technolog', 'konstruktor', 'wdrożeniowiec', 'QC']
    counts = []
    for r in roles:
        cnt = Step.query.filter(Step.status == 'todo', Step.required_roles.like(f'%{r}%')).count()
        counts.append(cnt)
    plt.figure(figsize=(6,4))
    plt.bar(roles, counts, color='salmon')
    plt.title('Zadania oczekujące wg roli')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_flow_chart():
    end_date = now_aware().date()
    start_date = end_date - timedelta(days=30)
    try:
        steps_done = Step.query.filter(Step.status == 'done', Step.status_updated_at >= start_date).all()
    except Exception:
        plt.figure(figsize=(10,4))
        plt.text(0.5, 0.5, 'Brak danych – kolumna status_updated_at niedostępna', ha='center', va='center')
        plt.title('Przepływ zadań')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    dates = [s.status_updated_at.date() for s in steps_done if s.status_updated_at]
    if not dates:
        plt.figure(figsize=(10,4))
        plt.text(0.5, 0.5, 'Brak danych za ostatnie 30 dni', ha='center', va='center')
        plt.title('Przepływ zadań – ilość ukończonych dziennie')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    df = pd.DataFrame({'date': dates})
    daily_counts = df.groupby('date').size().reindex(pd.date_range(start_date, end_date), fill_value=0)
    plt.figure(figsize=(12,5))
    plt.plot(daily_counts.index, daily_counts.values, marker='o', linestyle='-', color='green')
    plt.title('Przepływ zadań – liczba ukończonych kroków w ciągu ostatnich 30 dni')
    plt.xlabel('Data')
    plt.ylabel('Liczba ukończonych zadań')
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_bottleneck_chart():
    blocked_steps = Step.query.filter(Step.status.in_(['todo', 'in_progress', 'paused'])).all()
    blocked_count = sum(1 for s in blocked_steps if s.is_blocked())
    today = date.today()
    absent_users = User.query.filter(User.absence_start <= today, User.absence_end >= today).all()
    absent_user_ids = [u.id for u in absent_users]
    steps_assigned_to_absent = Step.query.filter(Step.assigned_user_id.in_(absent_user_ids), Step.status != 'done').count()
    categories = ['Zablokowane przez poprzednie', 'Przypisane do nieobecnych']
    counts = [blocked_count, steps_assigned_to_absent]
    plt.figure(figsize=(8,5))
    plt.bar(categories, counts, color=['orange', 'red'])
    plt.title('Wąskie gardła – zadania utrudniające postęp')
    plt.ylabel('Liczba zadań')
    for i, v in enumerate(counts):
        plt.text(i, v+0.2, str(v), ha='center')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_plan_vs_actual_chart():
    """Wykres porównania czasu planowanego vs rzeczywistego dla ukończonych zadań."""
    completed_steps = Step.query.filter(Step.status == 'done', Step.actual_hours.isnot(None)).order_by(Step.status_updated_at.desc()).limit(20).all()
    if not completed_steps:
        plt.figure(figsize=(10,6))
        plt.text(0.5, 0.5, 'Brak danych o czasie rzeczywistym dla ukończonych zadań', ha='center', va='center')
        plt.title('Planowane vs Rzeczywiste (brak danych)')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    names = [s.name[:20] for s in completed_steps]
    planned = [s.planned_hours for s in completed_steps]
    actual = [s.actual_hours for s in completed_steps]
    plt.figure(figsize=(12,6))
    x = range(len(names))
    width = 0.35
    plt.bar([i - width/2 for i in x], planned, width, label='Planowane', color='skyblue')
    plt.bar([i + width/2 for i in x], actual, width, label='Rzeczywiste', color='salmon')
    plt.xticks(x, names, rotation=45, ha='right')
    plt.ylabel('Godziny')
    plt.title('Porównanie czasu planowanego i rzeczywistego dla ukończonych zadań')
    plt.legend()
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# ----------------------------- POMOCNICZE -----------------------------
def can_user_manage_step(step, user):
    if user.is_admin:
        return True
    if step.assigned_user_id == user.id:
        return True
    if step.required_roles and user.has_any_role(step.required_roles):
        return True
    return False

def update_actual_hours_from_logs(step):
    """Oblicza i zapisuje actual_hours na podstawie wpisów TimeLog."""
    total_seconds = 0
    for log in step.time_logs:
        if log.end_time:
            start = ensure_aware(log.start_time)
            end = ensure_aware(log.end_time)
            delta = end - start
            total_seconds += delta.total_seconds()
    step.actual_hours = round(total_seconds / 3600, 1) if total_seconds else None
    db.session.add(step)

# ----------------------------- FUNKCJE DLA RAPORTÓW PDF -----------------------------
def get_user_tasks_in_period(user, start_date, end_date):
    """Zwraca zadania użytkownika (przypisane lub rola) w podziale na statusy, filtrowane po dacie aktualizacji statusu."""
    user_roles_names = [r.name for r in user.roles]
    if user_roles_names:
        role_conditions = [Step.required_roles.like(f'%{role}%') for role in user_roles_names]
        step_condition = db.or_(
            Step.assigned_user_id == user.id,
            db.and_(Step.required_roles.isnot(None), db.or_(*role_conditions))
        )
    else:
        step_condition = (Step.assigned_user_id == user.id)
    query = Step.query.filter(step_condition)
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        query = query.filter(Step.status_updated_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        query = query.filter(Step.status_updated_at <= end_dt)
    steps = query.all()
    return {
        'todo': [s for s in steps if s.status == 'todo'],
        'in_progress': [s for s in steps if s.status in ('in_progress', 'paused')],
        'done': [s for s in steps if s.status == 'done']
    }

def get_team_tasks_in_period(start_date, end_date):
    """Zwraca zadania wszystkich użytkowników (oraz nieprzypisane) w podziale na użytkowników i statusy."""
    query = Step.query
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        query = query.filter(Step.status_updated_at >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        query = query.filter(Step.status_updated_at <= end_dt)
    steps = query.all()
    user_tasks = {}
    for step in steps:
        if step.assigned_user:
            user = step.assigned_user
            if user not in user_tasks:
                user_tasks[user] = {'todo': [], 'in_progress': [], 'done': []}
            status_key = step.status if step.status != 'paused' else 'in_progress'
            user_tasks[user][status_key].append(step)
        else:
            if None not in user_tasks:
                user_tasks[None] = {'todo': [], 'in_progress': [], 'done': []}
            status_key = step.status if step.status != 'paused' else 'in_progress'
            user_tasks[None][status_key].append(step)
    return user_tasks

# ----------------------------- WIDOKI -----------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def dashboard():
    base_query = Step.query.options(
        joinedload(Step.project),
        joinedload(Step.assigned_user)
    ).join(Project).filter(
        ((Step.assigned_user_id == current_user.id) | (Step.assigned_user_id == None)),
        Project.is_archived == False
    )
    all_tasks = base_query.all()
    steps_todo = sum(1 for s in all_tasks if s.status == 'todo')
    steps_in_progress = sum(1 for s in all_tasks if s.status in ('in_progress', 'paused'))
    steps_done = sum(1 for s in all_tasks if s.status == 'done')
    active_tasks = [s for s in all_tasks if s.status in ('todo', 'in_progress', 'paused')]
    done_tasks = [s for s in all_tasks if s.status == 'done']
    priority_order = {'natychmiast': 1, 'pilny': 2, 'normalny': 3}
    active_tasks.sort(key=lambda s: priority_order.get(s.priority, 3))
    done_tasks.sort(key=lambda s: s.status_updated_at, reverse=True)
    my_tasks = active_tasks + done_tasks
    workload_chart = generate_workload_chart()
    roles_chart = generate_tasks_per_role_chart()
    return render_template('dashboard.html', user=current_user, my_tasks=my_tasks,
                           workload_chart=workload_chart, roles_chart=roles_chart,
                           steps_todo=steps_todo, steps_in_progress=steps_in_progress, steps_done=steps_done)

@app.route('/kanban')
@login_required
def kanban():
    base_query = Step.query.options(
        joinedload(Step.project),
        joinedload(Step.assigned_user)
    ).join(Project).filter(
        ((Step.assigned_user_id == current_user.id) | (Step.assigned_user_id == None)),
        Project.is_archived == False
    )
    all_tasks = base_query.all()
    tasks = {
        'todo': [t for t in all_tasks if t.status == 'todo'],
        'in_progress': [t for t in all_tasks if t.status in ('in_progress', 'paused')],
        'done': [t for t in all_tasks if t.status == 'done']
    }
    return render_template('kanban.html', tasks=tasks)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            log_action('LOGIN', f'Zalogowano użytkownika {user.username}')
            flash('Zalogowano pomyślnie.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    log_action('LOGOUT', f'Wylogowano użytkownika {current_user.username}')
    logout_user()
    flash('Wylogowano.', 'info')
    return redirect(url_for('login'))

# ------ Zarządzanie użytkownikami (admin) ------
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Użytkownik już istnieje.', 'danger')
            return redirect(url_for('add_user'))
        new_user = User(username=form.username.data, password=form.password.data, is_admin=form.is_admin.data,
                        absence_start=form.absence_start.data, absence_end=form.absence_end.data)
        role_name = form.roles.data
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)
            new_user.roles.append(role)
        db.session.add(new_user)
        db.session.commit()
        log_action('CREATE_USER', f'Utworzono użytkownika {new_user.username}')
        flash('Użytkownik dodany.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('user_form.html', form=form, title='Dodaj użytkownika')

@app.route('/admin/users/delete/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Nie możesz usunąć samego siebie.', 'danger')
        return redirect(url_for('admin_users'))
    log_action('DELETE_USER', f'Usunięto użytkownika {user.username}')
    db.session.delete(user)
    db.session.commit()
    flash('Użytkownik usunięty.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        old_name = user.username
        user.username = form.username.data
        if form.password.data:
            user.password = form.password.data
        user.is_admin = form.is_admin.data
        user.absence_start = form.absence_start.data
        user.absence_end = form.absence_end.data
        role_name = form.roles.data
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.session.add(role)
            user.roles = [role]
        db.session.commit()
        log_action('EDIT_USER', f'Zmodyfikowano użytkownika {old_name} -> {user.username}')
        flash('Zaktualizowano.', 'success')
        return redirect(url_for('admin_users'))
    form.roles.data = user.roles[0].name if user.roles else ''
    return render_template('user_form.html', form=form, title='Edytuj użytkownika')

# ------ Projekty ------
@app.route('/projects')
@login_required
def project_list():
    visible_steps_query = Step.query.options(joinedload(Step.project)).filter(
        ((Step.assigned_user_id == current_user.id) | (Step.assigned_user_id == None)),
        Project.is_archived == False
    ).join(Project)
    visible_project_ids = {s.project_id for s in visible_steps_query}
    projects = Project.query.filter(
        Project.is_archived == False,
        Project.id.in_(visible_project_ids)
    ).all()
    return render_template('projects.html', projects=projects)

@app.route('/projects/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_project():
    form = ProjectForm()
    all_templates = ProjectTemplate.query.order_by(ProjectTemplate.name).all()
    choices = [('', '-- brak --')] + [(f'db:{t.id}', t.name) for t in all_templates]
    form.template_choice.choices = choices
    if form.validate_on_submit():
        project = Project(name=form.name.data, description=form.description.data, deadline=form.deadline.data)
        db.session.add(project)
        db.session.commit()
        template_val = form.template_choice.data
        if template_val and template_val.startswith('db:'):
            tpl_id = int(template_val.split(':',1)[1])
            tpl = ProjectTemplate.query.get(tpl_id)
            if tpl:
                for step_tpl in tpl.steps:
                    step = Step(
                        name=step_tpl.name,
                        description=step_tpl.description,
                        planned_hours=step_tpl.planned_hours,
                        required_roles=step_tpl.required_roles,
                        position=step_tpl.position,
                        project_id=project.id,
                        status='todo',
                        status_updated_at=now_aware(),
                        priority='normalny'
                    )
                    db.session.add(step)
                db.session.commit()
                flash('Projekt utworzony z szablonu.', 'success')
                log_action('CREATE_PROJECT', f'Utworzono projekt "{project.name}" z szablonu {tpl.name}')
            else:
                flash('Projekt utworzony.', 'success')
        else:
            flash('Projekt utworzony. Możesz teraz dodać kroki.', 'success')
            log_action('CREATE_PROJECT', f'Utworzono projekt "{project.name}" bez szablonu')
        return redirect(url_for('project_steps', project_id=project.id))
    return render_template('project_form.html', form=form, title='Nowy projekt')

@app.route('/projects/<int:project_id>/steps')
@login_required
def project_steps(project_id):
    project = Project.query.get_or_404(project_id)
    steps = Step.query.filter_by(project_id=project_id).order_by(Step.position).all()
    can_edit = current_user.is_admin
    return render_template('project_steps.html', project=project, steps=steps, can_edit=can_edit)

@app.route('/projects/<int:project_id>/add_step', methods=['GET', 'POST'])
@login_required
@admin_required
def add_step(project_id):
    project = Project.query.get_or_404(project_id)
    form = StepForm()
    users = User.query.all()
    form.assigned_user_id.choices = [(0, '-- brak --')] + [(u.id, u.username) for u in users]
    form.step_template_id.choices = [(0, '-- brak --')] + [(st.id, st.name) for st in StepTemplate.query.filter_by(is_standalone=True).order_by(StepTemplate.name).all()]
    if form.validate_on_submit():
        max_pos = db.session.query(db.func.max(Step.position)).filter_by(project_id=project_id).scalar() or -1
        step = Step(
            name=form.name.data,
            description=form.description.data,
            planned_hours=form.planned_hours.data,
            required_roles=form.required_roles.data,
            assigned_user_id=form.assigned_user_id.data if form.assigned_user_id.data != 0 else None,
            project_id=project_id,
            position=max_pos+1,
            status='todo',
            status_updated_at=now_aware(),
            priority=form.priority.data
        )
        db.session.add(step)
        db.session.commit()
        log_action('CREATE_STEP', f'Dodano krok "{step.name}" do projektu "{project.name}"')
        flash('Krok dodany.', 'success')
        return redirect(url_for('project_steps', project_id=project_id))
    return render_template('step_form.html', form=form, project=project, title='Dodaj krok')

@app.route('/projects/<int:project_id>/edit_step/<int:step_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_step(project_id, step_id):
    step = Step.query.get_or_404(step_id)
    project = Project.query.get_or_404(project_id)
    form = StepForm(obj=step)
    users = User.query.all()
    form.assigned_user_id.choices = [(0, '-- brak --')] + [(u.id, u.username) for u in users]
    form.step_template_id.choices = [(0, '-- brak --')]
    if form.validate_on_submit():
        step.name = form.name.data
        step.description = form.description.data
        step.planned_hours = form.planned_hours.data
        step.required_roles = form.required_roles.data
        step.priority = form.priority.data
        new_assigned = form.assigned_user_id.data if form.assigned_user_id.data != 0 else None
        if step.assigned_user_id != new_assigned:
            step.assigned_user_id = new_assigned
        db.session.commit()
        log_action('EDIT_STEP', f'Zmodyfikowano krok "{step.name}" w projekcie "{project.name}"')
        flash('Krok zaktualizowany.', 'success')
        return redirect(url_for('project_steps', project_id=project_id))
    return render_template('step_form.html', form=form, project=project, step=step, title='Edytuj krok')

@app.route('/projects/<int:project_id>/delete_step/<int:step_id>')
@login_required
@admin_required
def delete_step(project_id, step_id):
    step = Step.query.get_or_404(step_id)
    project = step.project
    try:
        db.session.delete(step)
        remaining_steps = Step.query.filter_by(project_id=project_id).order_by(Step.position).all()
        for i, s in enumerate(remaining_steps):
            s.position = i
        db.session.commit()
        log_action('DELETE_STEP', f'Usunięto krok "{step.name}" z projektu "{project.name}"')
        flash('Krok usunięty.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Błąd podczas usuwania: {str(e)}', 'danger')
    return redirect(url_for('project_steps', project_id=project_id))

@app.route('/step/change_status/<int:step_id>/<status>', methods=['GET', 'POST'])
@login_required
def change_step_status(step_id, status):
    step = Step.query.get_or_404(step_id)
    allowed_statuses = ['todo', 'in_progress', 'paused', 'done']
    if status not in allowed_statuses:
        flash('Nieprawidłowy status.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
    if not can_user_manage_step(step, current_user):
        flash('Nie masz uprawnień do zmiany statusu tego kroku.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
    if status == 'done' and not step.can_be_started():
        flash('Nie możesz ukończyć tego kroku, ponieważ poprzednie nie są zakończone.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))
    
    old_status = step.status
    now = now_aware()
    
    # Logika TimeLog
    if status == 'in_progress' and old_status != 'in_progress':
        active_log = TimeLog.query.filter_by(step_id=step.id, end_time=None).first()
        if not active_log:
            tl = TimeLog(step_id=step.id, user_id=current_user.id, start_time=now)
            db.session.add(tl)
    elif status == 'paused' and old_status == 'in_progress':
        active_log = TimeLog.query.filter_by(step_id=step.id, end_time=None).first()
        if active_log:
            active_log.end_time = now
            db.session.add(active_log)
    elif status == 'done':
        active_log = TimeLog.query.filter_by(step_id=step.id, end_time=None).first()
        if active_log:
            active_log.end_time = now
            db.session.add(active_log)
        update_actual_hours_from_logs(step)
    elif status == 'todo' and old_status in ('in_progress', 'paused'):
        active_log = TimeLog.query.filter_by(step_id=step.id, end_time=None).first()
        if active_log:
            db.session.delete(active_log)
        step.actual_hours = None
    
    step.status = status
    step.status_updated_at = now
    db.session.commit()
    
    log_action('CHANGE_STATUS', f'Zmiana statusu zadania "{step.name}" z {old_status} na {status} przez {current_user.username}')
    project = step.project
    all_done = all(s.status == 'done' for s in project.steps)
    if all_done:
        flash(f'Projekt "{project.name}" został ukończony!', 'success')
    flash(f'Status zmieniony na {status}.', 'success')
    return redirect(request.referrer or url_for('dashboard'))

# ------ Archiwum ------
@app.route('/admin/archive')
@login_required
@admin_required
def archive():
    archived_projects = Project.query.filter_by(is_archived=True).all()
    return render_template('archive.html', projects=archived_projects)

@app.route('/admin/archive_project/<int:project_id>')
@login_required
@admin_required
def archive_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.is_archived = True
    db.session.commit()
    log_action('ARCHIVE_PROJECT', f'Zarchiwizowano projekt "{project.name}"')
    flash('Projekt przeniesiony do archiwum.', 'success')
    return redirect(url_for('project_list'))

@app.route('/admin/restore_project/<int:project_id>')
@login_required
@admin_required
def restore_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.is_archived = False
    db.session.commit()
    log_action('RESTORE_PROJECT', f'Przywrócono projekt "{project.name}" z archiwum')
    flash('Projekt przywrócony z archiwum.', 'success')
    return redirect(url_for('archive'))

@app.route('/admin/delete_project/<int:project_id>')
@login_required
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    log_action('DELETE_PROJECT', f'Trwale usunięto projekt "{project.name}"')
    db.session.delete(project)
    db.session.commit()
    flash('Projekt trwale usunięty.', 'success')
    return redirect(url_for('archive'))

# ------ Kalendarz ------
@app.route('/calendar')
@login_required
def calendar_view():
    projects = Project.query.filter(Project.deadline.isnot(None)).all()
    events = []
    for p in projects:
        if p.deadline:
            events.append({
                'title': f'Termin: {p.name}',
                'start': p.deadline.isoformat(),
                'allDay': True,
                'color': 'red'
            })
    if current_user.is_admin:
        users = User.query.filter((User.absence_start.isnot(None)) | (User.absence_end.isnot(None))).all()
    else:
        users = [current_user]
    for u in users:
        if u.absence_start and u.absence_end:
            events.append({
                'title': f'Nieobecność: {u.username}',
                'start': u.absence_start.isoformat(),
                'end': (u.absence_end + timedelta(days=1)).isoformat(),
                'allDay': True,
                'color': 'orange'
            })
    return render_template('calendar.html', events=events)

# ------ Wykresy (rozszerzone) ------
@app.route('/charts')
@login_required
def charts():
    workload_chart = generate_workload_chart()
    roles_chart = generate_tasks_per_role_chart()
    flow_chart = generate_flow_chart()
    bottleneck_chart = generate_bottleneck_chart()
    plan_vs_actual_chart = generate_plan_vs_actual_chart()
    return render_template('charts.html', workload_chart=workload_chart, roles_chart=roles_chart,
                           flow_chart=flow_chart, bottleneck_chart=bottleneck_chart,
                           plan_vs_actual_chart=plan_vs_actual_chart)

# ------ DZIENNIK ZDARZEŃ (tylko admin) ------
@app.route('/admin/logs')
@login_required
@admin_required
def view_logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('logs.html', logs=logs)

# ------ GENEROWANIE RAPORTÓW PDF ------
@app.route('/my_tasks_pdf')
@login_required
def my_tasks_pdf():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    start_date = None
    end_date = None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    tasks = get_user_tasks_in_period(current_user, start_date, end_date)
    html_content = render_template('tasks_pdf.html',
                                   user=current_user,
                                   tasks=tasks,
                                   start_date=start_date,
                                   end_date=end_date,
                                   report_type='user',
                                   now=datetime.now())
    pdf_file = HTML(string=html_content).write_pdf()
    response = make_response(pdf_file)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=moje_zadania_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    return response

@app.route('/team_tasks_pdf')
@login_required
@admin_required
def team_tasks_pdf():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    start_date = None
    end_date = None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    tasks_by_user = get_team_tasks_in_period(start_date, end_date)
    html_content = render_template('tasks_pdf.html',
                                   tasks_by_user=tasks_by_user,
                                   start_date=start_date,
                                   end_date=end_date,
                                   report_type='team',
                                   now=datetime.now())
    pdf_file = HTML(string=html_content).write_pdf()
    response = make_response(pdf_file)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=raport_zespolu_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    return response

# ---------- ZARZĄDZANIE SZABLONAMI PROJEKTÓW (admin) ----------
@app.route('/admin/templates/projects')
@login_required
@admin_required
def list_project_templates():
    templates = ProjectTemplate.query.order_by(ProjectTemplate.name).all()
    return render_template('admin_project_templates.html', templates=templates)

@app.route('/admin/templates/projects/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_project_template():
    form = ProjectTemplateForm()
    if form.validate_on_submit():
        tpl = ProjectTemplate(name=form.name.data, description=form.description.data, is_builtin=False)
        db.session.add(tpl)
        db.session.commit()
        flash('Szablon projektu utworzony. Możesz teraz dodać do niego kroki.', 'success')
        return redirect(url_for('edit_project_template', template_id=tpl.id))
    return render_template('project_template_form.html', form=form, title='Nowy szablon projektu')

@app.route('/admin/templates/projects/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_project_template(template_id):
    tpl = ProjectTemplate.query.get_or_404(template_id)
    form = ProjectTemplateForm(obj=tpl)
    if form.validate_on_submit():
        tpl.name = form.name.data
        tpl.description = form.description.data
        db.session.commit()
        flash('Szablon zaktualizowany.', 'success')
        return redirect(url_for('list_project_templates'))
    return render_template('project_template_form.html', form=form, title='Edytuj szablon projektu', template=tpl)

@app.route('/admin/templates/projects/<int:template_id>/delete')
@login_required
@admin_required
def delete_project_template(template_id):
    tpl = ProjectTemplate.query.get_or_404(template_id)
    db.session.delete(tpl)
    db.session.commit()
    flash('Szablon usunięty.', 'success')
    return redirect(url_for('list_project_templates'))

@app.route('/admin/templates/projects/<int:template_id>/steps/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_step_to_template(template_id):
    tpl = ProjectTemplate.query.get_or_404(template_id)
    form = StepTemplateForm()
    if form.validate_on_submit():
        max_pos = db.session.query(db.func.max(StepTemplate.position)).filter_by(template_id=template_id).scalar() or -1
        step = StepTemplate(
            name=form.name.data,
            description=form.description.data,
            planned_hours=form.planned_hours.data,
            required_roles=form.required_roles.data,
            position=max_pos+1,
            template_id=template_id,
            is_standalone=False
        )
        db.session.add(step)
        db.session.commit()
        flash('Krok dodany do szablonu.', 'success')
        return redirect(url_for('edit_project_template', template_id=template_id))
    return render_template('step_template_form.html', form=form, title='Dodaj krok do szablonu', template=tpl)

@app.route('/admin/templates/projects/steps/<int:step_id>/delete')
@login_required
@admin_required
def delete_step_from_template(step_id):
    step = StepTemplate.query.get_or_404(step_id)
    tpl_id = step.template_id
    db.session.delete(step)
    remaining = StepTemplate.query.filter_by(template_id=tpl_id).order_by(StepTemplate.position).all()
    for i, s in enumerate(remaining):
        s.position = i
    db.session.commit()
    flash('Krok usunięty.', 'success')
    return redirect(url_for('edit_project_template', template_id=tpl_id))

# ---------- ZARZĄDZANIE SZABLONAMI KROKÓW (samodzielne) ----------
@app.route('/admin/templates/steps')
@login_required
@admin_required
def list_step_templates():
    steps = StepTemplate.query.filter_by(is_standalone=True).order_by(StepTemplate.name).all()
    return render_template('admin_step_templates.html', steps=steps)

@app.route('/admin/templates/steps/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_step_template():
    form = StepTemplateForm()
    if form.validate_on_submit():
        step = StepTemplate(
            name=form.name.data,
            description=form.description.data,
            planned_hours=form.planned_hours.data,
            required_roles=form.required_roles.data,
            is_standalone=True
        )
        db.session.add(step)
        db.session.commit()
        flash('Szablon kroku dodany.', 'success')
        return redirect(url_for('list_step_templates'))
    return render_template('step_template_form.html', form=form, title='Nowy szablon kroku')

@app.route('/admin/templates/steps/<int:step_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_step_template(step_id):
    step = StepTemplate.query.get_or_404(step_id)
    if not step.is_standalone:
        flash('Ten krok należy do szablonu projektu i nie może być edytowany oddzielnie.', 'danger')
        return redirect(url_for('list_step_templates'))
    form = StepTemplateForm(obj=step)
    if form.validate_on_submit():
        step.name = form.name.data
        step.description = form.description.data
        step.planned_hours = form.planned_hours.data
        step.required_roles = form.required_roles.data
        db.session.commit()
        flash('Szablon kroku zaktualizowany.', 'success')
        return redirect(url_for('list_step_templates'))
    return render_template('step_template_form.html', form=form, title='Edytuj szablon kroku', step=step)

@app.route('/admin/templates/steps/<int:step_id>/delete')
@login_required
@admin_required
def delete_step_template(step_id):
    step = StepTemplate.query.get_or_404(step_id)
    if not step.is_standalone:
        flash('Nie można usunąć kroku należącego do szablonu projektu.', 'danger')
        return redirect(url_for('list_step_templates'))
    db.session.delete(step)
    db.session.commit()
    flash('Szablon kroku usunięty.', 'success')
    return redirect(url_for('list_step_templates'))

# ---------- API dla szablonu kroku ----------
@app.route('/api/step_template/<int:template_id>')
@login_required
def api_step_template(template_id):
    st = StepTemplate.query.get_or_404(template_id)
    return jsonify({
        'name': st.name,
        'description': st.description or '',
        'planned_hours': st.planned_hours,
        'required_roles': st.required_roles or ''
    })

# ---------- Sprawdzenie produkcji (Check-lista z ERPXL) ----------
@app.route('/sprawdzenie_produkcji')
@login_required
@role_required('technolog')
def sprawdzenie_produkcji():
    today = date.today()
    two_weeks_forward = today + timedelta(days=14)
    
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(two_weeks_forward, datetime.max.time())
    
    items = ProductionCheck.query.filter(
        ProductionCheck.data_aktywacji >= start_dt,
        ProductionCheck.data_aktywacji <= end_dt
    ).order_by(ProductionCheck.data_aktywacji.asc(), ProductionCheck.row_number.asc()).all()
    
    total_count = len(items)
    checked_count = sum(1 for item in items if item.sprawdzono)
    unchecked_count = total_count - checked_count
    progress_pct = round((checked_count / total_count * 100), 1) if total_count > 0 else 0
    
    return render_template('sprawdzenie_produkcji.html',
                           items=items,
                           total_count=total_count,
                           checked_count=checked_count,
                           unchecked_count=unchecked_count,
                           progress_pct=progress_pct,
                           today=today,
                           two_weeks_forward=two_weeks_forward)

@app.route('/sprawdzenie_produkcji/sync', methods=['POST'])
@login_required
@role_required('technolog')
def sprawdzenie_produkcji_sync():
    try:
        from poleczenie_erpxl import pobierz_dane_erpxl
        df = pobierz_dane_erpxl()
        if df is None or df.empty:
            flash("Baza danych ERPXL zwróciła pusty wynik.", "warning")
            return redirect(url_for('sprawdzenie_produkcji'))
            
        today = date.today()
        two_weeks_forward = today + timedelta(days=14)
        
        # Filtrowanie w Pandas dla optymalizacji wydajności:
        # Konwertujemy kolumnę "Data aktywacji" na datetime
        df['Data_parsed'] = pd.to_datetime(df['Data aktywacji'], errors='coerce')
        
        # Interesują nas wpisy w zakresie [today, today + 14 dni]
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(two_weeks_forward, datetime.max.time())
        
        df_filtered = df[(df['Data_parsed'] >= start_dt) & (df['Data_parsed'] <= end_dt)]
        
        inserted = 0
        updated = 0
        
        for _, row in df_filtered.iterrows():
            pzl_id_val = str(row['PZL_ID'])
            prod_kod_val = str(row['Prod_Kod']) if pd.notna(row['Prod_Kod']) else None
            zp_val = str(row['ZP']) if pd.notna(row['ZP']) else None
            dizallzp_val = str(row['DizałlZP']) if pd.notna(row['DizałlZP']) else None
            data_akt_dt = row['Data_parsed'].to_pydatetime() if pd.notna(row['Data_parsed']) else None
            row_num_val = int(row['RowNumber']) if pd.notna(row['RowNumber']) else None
            
            # Pobieramy wpis z sesji
            item = db.session.get(ProductionCheck, pzl_id_val)
            if item:
                item.prod_kod = prod_kod_val
                item.zp = zp_val
                item.dizallzp = dizallzp_val
                item.data_aktywacji = data_akt_dt
                item.row_number = row_num_val
                updated += 1
            else:
                new_item = ProductionCheck(
                    pzl_id=pzl_id_val,
                    prod_kod=prod_kod_val,
                    zp=zp_val,
                    dizallzp=dizallzp_val,
                    data_aktywacji=data_akt_dt,
                    row_number=row_num_val,
                    sprawdzono=False
                )
                db.session.add(new_item)
                inserted += 1
                
        db.session.commit()
        log_action('SYNC_ERPX_PLAN', f'Zsynchronizowano plan produkcyjny. Nowe: {inserted}, zaktualizowane: {updated}')
        flash(f"Dane zaktualizowane pomyślnie! Dodano {inserted} nowych, zaktualizowano {updated}.", "success")
    except Exception as e:
        db.session.rollback()
        log_action('SYNC_ERPX_PLAN_ERROR', f'Błąd podczas aktualizacji planu: {str(e)}')
        flash(f"Błąd podczas połączenia z ERPXL: {str(e)}", "danger")
        
    return redirect(url_for('sprawdzenie_produkcji'))

@app.route('/sprawdzenie_produkcji/toggle', methods=['POST'])
@login_required
@role_required('technolog')
def sprawdzenie_produkcji_toggle():
    data = request.get_json()
    if not data or 'pzl_id' not in data:
        return jsonify({'status': 'error', 'message': 'Brak PZL_ID'}), 400
        
    pzl_id_val = str(data.get('pzl_id'))
    checked_val = bool(data.get('checked', False))
    
    item = ProductionCheck.query.get(pzl_id_val)
    if not item:
        return jsonify({'status': 'error', 'message': 'Pozycja nie istnieje'}), 404
        
    item.sprawdzono = checked_val
    if checked_val:
        item.checked_by = current_user.username
        item.checked_at = now_aware()
    else:
        item.checked_by = None
        item.checked_at = None
        
    db.session.commit()
    log_action('TOGGLE_PROD_CHECK', f'Zmieniono status PZL_ID {pzl_id_val} na {checked_val}')
    return jsonify({'status': 'success', 'sprawdzono': item.sprawdzono})

# ----------------------------- INICJALIZACJA BAZY -----------------------------
def init_db():
    db.create_all()
    
    # Dodanie brakujących kolumn (dla bezpieczeństwa)
    try:
        with app.app_context():
            result = db.session.execute(text("PRAGMA table_info(step)"))
            columns = [row[1] for row in result.fetchall()]
            if 'status_updated_at' not in columns:
                db.session.execute(text("ALTER TABLE step ADD COLUMN status_updated_at DATETIME"))
            if 'priority' not in columns:
                db.session.execute(text("ALTER TABLE step ADD COLUMN priority VARCHAR(20) DEFAULT 'normalny'"))
            if 'started_at' not in columns:
                db.session.execute(text("ALTER TABLE step ADD COLUMN started_at DATETIME"))
            if 'actual_hours' not in columns:
                db.session.execute(text("ALTER TABLE step ADD COLUMN actual_hours FLOAT"))
            
            result_pc = db.session.execute(text("PRAGMA table_info(production_check)"))
            columns_pc = [row[1] for row in result_pc.fetchall()]
            if 'dizallzp' not in columns_pc:
                db.session.execute(text("ALTER TABLE production_check ADD COLUMN dizallzp VARCHAR(200)"))
            db.session.commit()
    except Exception as e:
        print("Błąd podczas dodawania kolumn:", e)
    
    # Konwersja istniejących naiwnych datetime na świadome UTC
    def fix_datetime_awareness():
        try:
            for step in Step.query.all():
                step.status_updated_at = ensure_aware(step.status_updated_at)
                if step.started_at:
                    step.started_at = ensure_aware(step.started_at)
            for project in Project.query.all():
                project.created_at = ensure_aware(project.created_at)
            for log in LogEntry.query.all():
                log.timestamp = ensure_aware(log.timestamp)
            for tlog in TimeLog.query.all():
                tlog.start_time = ensure_aware(tlog.start_time)
                if tlog.end_time:
                    tlog.end_time = ensure_aware(tlog.end_time)
            db.session.commit()
            print("Konwersja datetime na świadome UTC zakończona.")
        except Exception as e:
            print("Migracja datetime nie jest potrzebna lub wystąpił błąd:", e)
    
    fix_datetime_awareness()
    
    # Uzupełnienie brakujących status_updated_at (jeśli jeszcze jakieś są)
    try:
        steps_without_date = Step.query.filter(Step.status_updated_at == None).all()
        for step in steps_without_date:
            step.status_updated_at = ensure_aware(step.project.created_at) if step.project else now_aware()
        db.session.commit()
    except Exception as e:
        print("Błąd podczas aktualizacji status_updated_at:", e)
    
    # Dodanie domyślnych ról
    for role_name in ['technolog', 'konstruktor', 'wdrożeniowiec', 'QC']:
        if not Role.query.filter_by(name=role_name).first():
            db.session.add(Role(name=role_name))
    
    # Dodanie domyślnych użytkowników
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin', is_admin=True)
        db.session.add(admin)
        user1 = User(username='technolog1', password='pass', is_admin=False)
        db.session.add(user1)
        db.session.commit()
        admin.roles.append(Role.query.filter_by(name='technolog').first())
        user1.roles.append(Role.query.filter_by(name='technolog').first())
        db.session.commit()
    
    # Dodanie trzech początkowych szablonów
    templates_data = {
        "szablon1": [
            {"name": "Analiza zapytania klienta", "required_roles": "technolog", "planned_hours": 2},
            {"name": "Przygotowanie „szacowanych” plików do kroju z informacją o długości łączeń", "required_roles": "konstruktor", "planned_hours": 4},
            {"name": "Opracowanie wstępnego BOM", "required_roles": "technolog", "planned_hours": 3},
            {"name": "Oszacowanie czasów produktów", "required_roles": "technolog", "planned_hours": 2},
            {"name": "Przygotowanie wstępnej wyceny", "required_roles": "technolog", "planned_hours": 1},
            {"name": "Weryfikacja dostępności materiałów i komponentów", "required_roles": "technolog", "planned_hours": 2},
            {"name": "Konsultacja z technologiem", "required_roles": "technolog", "planned_hours": 1}
        ],
        "szablon2": [
            {"name": "Tłumaczenie rysunku + weryfikacja, czy są wszystkie istotne informacje", "required_roles": "konstruktor", "planned_hours": 3},
            {"name": "Opracowanie plików do kroju", "required_roles": "konstruktor", "planned_hours": 5},
            {"name": "Przygotowanie układu (na 1 szt. i na najbardziej optymalną ilość)", "required_roles": "konstruktor", "planned_hours": 3},
            {"name": "Przygotowanie schematu łączenia", "required_roles": "konstruktor", "planned_hours": 2},
            {"name": "Opracowanie BOM w ERP", "required_roles": "technolog", "planned_hours": 2},
            {"name": "Ustalenie czasów produkcji z odpowiednim podziałem na procesy", "required_roles": "technolog", "planned_hours": 2},
            {"name": "Wgranie dokumentacji do MobiDoc (informacje o etykiecie i pakowaniu)", "required_roles": "technolog", "planned_hours": 1}
        ],
        "szablon3": [
            {"name": "Omówienie produktu z konstruktorem i technologiem", "required_roles": "technolog,konstruktor,wdrożeniowiec", "planned_hours": 1},
            {"name": "Produkcja pierwszej sztuki", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 4},
            {"name": "Kontrola wstępna z konstruktorem i technologiem", "required_roles": "technolog,konstruktor,wdrożeniowiec", "planned_hours": 1},
            {"name": "Wykonanie zdjęć", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 1},
            {"name": "Przygotowanie instrukcji krok po kroku", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 3},
            {"name": "Aktualizacja BOM (w porozumieniu z technologiem)", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 2},
            {"name": "Przygotowanie kompletnej dokumentacji (MobiDoc)", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 2},
            {"name": "Akceptacja dokumentacji – spotkanie z konstruktorem, technologiem i liderem produkcji", "required_roles": "technolog,konstruktor,wdrożeniowiec", "planned_hours": 1},
            {"name": "Akceptacja dokumentacji – kontrola finalna QC", "required_roles": "QC", "planned_hours": 1},
            {"name": "Informacja / przekazanie technologii na dział produkcyjny", "required_roles": "technolog,wdrożeniowiec", "planned_hours": 1}
        ]
    }
    for name, steps_data in templates_data.items():
        tpl = ProjectTemplate.query.filter_by(name=name).first()
        if not tpl:
            tpl = ProjectTemplate(name=name, is_builtin=False)
            db.session.add(tpl)
            db.session.flush()
            for idx, step_data in enumerate(steps_data):
                step_tpl = StepTemplate(
                    name=step_data['name'],
                    required_roles=step_data['required_roles'],
                    planned_hours=step_data['planned_hours'],
                    position=idx,
                    template_id=tpl.id,
                    is_standalone=False
                )
                db.session.add(step_tpl)
            db.session.commit()
            print(f"Dodano szablon '{name}' do bazy jako zwykły (edytowalny).")
    
    print("Baza danych zainicjalizowana.")

# ----------------------------- URUCHOMIENIE -----------------------------
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)