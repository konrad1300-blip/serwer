from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, IntegerField, FieldList, FormField, BooleanField
from wtforms.validators import DataRequired, Regexp, NumberRange, Optional

class GrupaForm(FlaskForm):
    nazwa = StringField('Nazwa grupy', validators=[DataRequired()])

class MetodaForm(FlaskForm):
    nazwa = SelectField('Metoda', choices=[], validators=[DataRequired()])

class CzasPrzedzialuForm(FlaskForm):
    przedzial = StringField('Przedział')
    pracownicy = IntegerField('Liczba pracowników', default=1, validators=[NumberRange(min=1, max=20)])
    czas = FloatField('Czas na metr (min)', default=0.0, validators=[NumberRange(min=0)])

class MetodaEdycjaForm(FlaskForm):
    czasy = FieldList(FormField(CzasPrzedzialuForm))

class ObliczeniaForm(FlaskForm):
    kod = StringField('Kod produktu', validators=[
        DataRequired(),
        Regexp(r'^\d{3}-\d{4}-\d{3}$', message='Format: xxx-xxxx-xxx (same cyfry)')
    ])
    grupa_id = SelectField('Grupa', coerce=int, validators=[DataRequired()])
    przedzial = SelectField('Przedział wielkości', choices=[
        ('do 2m2', 'do 2m2'),
        ('od 2 do 20m2', 'od 2 do 20m2'),
        ('od 20 do 60m2', 'od 20 do 60m2'),
        ('powyżej 60m2', 'powyżej 60m2')
    ], validators=[DataRequired()])

class MetryForm(FlaskForm):
    metoda_id = IntegerField()
    metry = FloatField('Metry', default=0.0, validators=[Optional(), NumberRange(min=0)])
    wymus_pracownikow = BooleanField('Wymuś pracowników')
    liczba_pracownikow = IntegerField('Liczba', default=1, validators=[Optional(), NumberRange(min=1, max=10)])

class WalidacjaForm(FlaskForm):
    czas_produkcji = FloatField('Czas z produkcji (min)', validators=[DataRequired(), NumberRange(min=0)])