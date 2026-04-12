from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import Grupa, Metoda, MetodaCzas
from app.forms import MetodaForm, MetodaEdycjaForm, CzasPrzedzialuForm

bp = Blueprint('methods', __name__)

PRZEDZIALY = ["do 2m2", "od 2 do 20m2", "od 20 do 60m2", "powyżej 60m2"]

@bp.route('/grupa/<int:grupa_id>')
def list(grupa_id):
    grupa = Grupa.query.get_or_404(grupa_id)
    return render_template('methods/list.html', grupa=grupa, przedzialy=PRZEDZIALY)

@bp.route('/dodaj/<int:grupa_id>', methods=['GET', 'POST'])
def add(grupa_id):
    grupa = Grupa.query.get_or_404(grupa_id)
    form = MetodaForm()
    # Ustaw dostępne metody (tylko te, których jeszcze nie ma w grupie)
    istniejace = {m.nazwa for m in grupa.metody}
    wszystkie = Grupa.domyslne_metody()  # poprawione: Grupa.domyslne_metody()
    dostepne = [(n, n) for n in wszystkie if n not in istniejace]
    form.nazwa.choices = dostepne
    if form.validate_on_submit():
        nazwa = form.nazwa.data
        metoda = Metoda(nazwa=nazwa, grupa_id=grupa.id)
        db.session.add(metoda)
        db.session.flush()

        # Dodaj domyślne czasy
        domyslne = Metoda.domyslne_czasy().get(nazwa, {})
        for przedzial in PRZEDZIALY:
            prac, czas = domyslne.get(przedzial, (1, 0.0))
            mc = MetodaCzas(
                metoda_id=metoda.id,
                przedzial=przedzial,
                pracownicy=prac,
                czas_na_metr=czas
            )
            db.session.add(mc)
        db.session.commit()
        flash(f'Metoda {nazwa} została dodana.', 'success')
        return redirect(url_for('methods.list', grupa_id=grupa.id))
    return render_template('methods/add.html', form=form, grupa=grupa)


@bp.route('/edytuj/<int:metoda_id>', methods=['GET', 'POST'])
def edit(metoda_id):
    metoda = Metoda.query.get_or_404(metoda_id)
    grupa = metoda.grupa

    # Przygotuj formularz z czasami
    form = MetodaEdycjaForm()
    # Wypełnij polami dla każdego przedziału
    for przedzial in PRZEDZIALY:
        czas_obj = next((c for c in metoda.czasy if c.przedzial == przedzial), None)
        prac = czas_obj.pracownicy if czas_obj else 1
        czas = czas_obj.czas_na_metr if czas_obj else 0.0
        form.czasy.append_entry({
            'przedzial': przedzial,
            'pracownicy': prac,
            'czas': czas
        })

    if form.validate_on_submit():
        # Aktualizuj czasy
        for entry in form.czasy.entries:
            przedzial = entry.przedzial.data
            prac = entry.pracownicy.data
            czas = entry.czas.data
            # Znajdź istniejący lub utwórz nowy
            mc = MetodaCzas.query.filter_by(metoda_id=metoda.id, przedzial=przedzial).first()
            if not mc:
                mc = MetodaCzas(metoda_id=metoda.id, przedzial=przedzial)
                db.session.add(mc)
            mc.pracownicy = prac
            mc.czas_na_metr = czas
        db.session.commit()
        flash('Czasy metody zostały zaktualizowane.', 'success')
        return redirect(url_for('methods.list', grupa_id=grupa.id))

    return render_template('methods/edit.html', form=form, metoda=metoda, grupa=grupa)

@bp.route('/usun/<int:metoda_id>', methods=['POST'])
def delete(metoda_id):
    metoda = Metoda.query.get_or_404(metoda_id)
    grupa_id = metoda.grupa_id
    db.session.delete(metoda)
    db.session.commit()
    flash('Metoda została usunięta.', 'success')
    return redirect(url_for('methods.list', grupa_id=grupa_id))