from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import Grupa
from app.forms import GrupaForm

bp = Blueprint('groups', __name__)

@bp.route('/')
def list():
    grupy = Grupa.query.order_by(Grupa.nazwa).all()
    return render_template('groups/list.html', grupy=grupy)

@bp.route('/dodaj', methods=['GET', 'POST'])
def add():
    form = GrupaForm()
    if form.validate_on_submit():
        nazwa = form.nazwa.data
        if Grupa.query.filter_by(nazwa=nazwa).first():
            flash('Grupa o tej nazwie już istnieje.', 'danger')
            return render_template('groups/add.html', form=form)
        grupa = Grupa(nazwa=nazwa)
        db.session.add(grupa)
        db.session.commit()
        flash('Grupa została dodana.', 'success')
        return redirect(url_for('groups.list'))
    return render_template('groups/add.html', form=form)

@bp.route('/edytuj/<int:id>', methods=['GET', 'POST'])
def edit(id):
    grupa = Grupa.query.get_or_404(id)
    form = GrupaForm(obj=grupa)
    if form.validate_on_submit():
        if form.nazwa.data != grupa.nazwa and Grupa.query.filter_by(nazwa=form.nazwa.data).first():
            flash('Grupa o tej nazwie już istnieje.', 'danger')
            return render_template('groups/edit.html', form=form, grupa=grupa)
        grupa.nazwa = form.nazwa.data
        db.session.commit()
        flash('Grupa została zaktualizowana.', 'success')
        return redirect(url_for('groups.list'))
    return render_template('groups/edit.html', form=form, grupa=grupa)

@bp.route('/usun/<int:id>', methods=['POST'])
def delete(id):
    grupa = Grupa.query.get_or_404(id)
    db.session.delete(grupa)
    db.session.commit()
    flash('Grupa została usunięta.', 'success')
    return redirect(url_for('groups.list'))