from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, FloatField, RadioField
from wtforms.validators import DataRequired, NumberRange, Regexp

class QcReportForm(FlaskForm):
    product_number = StringField('Numer produktu (xxx-xxxx-xxx)', validators=[
        DataRequired(),
        Regexp(r'^\d{3}-\d{4}-\d{3}$', message='Format: xxx-xxxx-xxx (tylko cyfry)')
    ])
    shipping_direction = SelectField('Kierunek wysyłki', choices=[('UE', 'UE'), ('Poza UE', 'Poza UE')])
    pallet_type = SelectField('Rodzaj palety', choices=[
        ('PLL EURO', 'PLL EURO'),
        ('PLL #', 'PLL #'),
        ('PLL Specj.', 'PLL Specj.'),
        ('ROLL', 'ROLL'),
        ('PCKG Paczka', 'PCKG Paczka'),
        ('PLL ½', 'PLL ½'),
        ('EURO Karton', 'EURO Karton'),
        ('PLL # Karton', 'PLL # Karton')
    ])
    certified = RadioField('Paleta certyfikowana', choices=[('TAK', 'TAK'), ('NIE', 'NIE')], default='NIE')
    pallet_size = StringField('Rozmiar palety (dł.xszer.xwys. mm)', validators=[
        DataRequired(),
        Regexp(r'^\d+x\d+x\d+$', message='Format: długośćxszerokośćxwysokość (np. 1200x800x115)')
    ])
    extensions = IntegerField('Ilość nadstawek', default=0, validators=[NumberRange(min=0, max=20)])
    cartons = IntegerField('Ilość kartonów', default=1, validators=[NumberRange(min=0, max=10000)])
    products = IntegerField('Ilość produktów (przy 0 kartonów)', default=0, validators=[NumberRange(min=0, max=10000)])
    max_per_pallet = IntegerField('Maks. na palecie', default=1, validators=[NumberRange(min=1, max=1000)])
    stack_type = SelectField('Rodzaj układania', choices=[('płasko', 'płasko'), ('rolowanie', 'rolowanie')])
    unit_weight = FloatField('Waga jednej sztuki (kg)', validators=[DataRequired(), NumberRange(min=0)])
    reporter = SelectField('Kontroler', choices=[], validators=[DataRequired()])  # wypełniane dynamicznie