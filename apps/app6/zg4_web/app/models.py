import json
from datetime import datetime

from app import db

# Tabela asocjacyjna dla metod i ich czasów
class MetodaCzas(db.Model):
    __tablename__ = 'metoda_czasy'
    id = db.Column(db.Integer, primary_key=True)
    metoda_id = db.Column(db.Integer, db.ForeignKey('metoda.id'))
    przedzial = db.Column(db.String(50))  # np. "do 2m2"
    pracownicy = db.Column(db.Integer, default=1)
    czas_na_metr = db.Column(db.Float, default=0.0)

class Metoda(db.Model):
    __tablename__ = 'metoda'
    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(100), nullable=False)
    grupa_id = db.Column(db.Integer, db.ForeignKey('grupa.id'))

    czasy = db.relationship('MetodaCzas', backref='metoda', cascade='all, delete-orphan')

    @staticmethod
    def domyslne_czasy():
        """Zwraca domyślne czasy dla metody o danej nazwie (słownik)."""
        return {
            "HF Duży (ZEMAT)": {
                "do 2m2": (1, 2.0),
                "od 2 do 20m2": (1, 3.0),
                "od 20 do 60m2": (2, 2.0),
                "powyżej 60m2": (3, 3.0)
            },
            "HF Mały (WOLDAN)": {
                "do 2m2": (1, 2.0),
                "od 2 do 20m2": (1, 3.0),
                "od 20 do 60m2": (2, 2.0),
                "powyżej 60m2": (3, 3.0)
            },
            "Gorące Powietrze (MILLER)": {
                "do 2m2": (1, 1.5),
                "od 2 do 20m2": (2, 1.5),
                "od 20 do 60m2": (3, 1.5),
                "powyżej 60m2": (4, 2.0)
            },
            "Gorące Powietrze (Ręcznie)": {
                "do 2m2": (1, 3.0),
                "od 2 do 20m2": (1, 5.0),
                "od 20 do 60m2": (2, 4.0),
                "powyżej 60m2": (3, 5.0)
            },
            "Gorące Powietrze (Zgrzewarka jezdna)": {
                "do 2m2": (1, 1.5),
                "od 2 do 20m2": (2, 2.0),
                "od 20 do 60m2": (3, 3.0),
                "powyżej 60m2": (4, 4.0)
            },
            "Gorące Powietrze (ASATECH)": {
                "do 2m2": (1, 1.5),
                "od 2 do 20m2": (2, 2.0),
                "od 20 do 60m2": (3, 3.0),
                "powyżej 60m2": (4, 4.0)
            },
            "Gorący Klin (SEAMTEC)": {
                "do 2m2": (1, 1.5),
                "od 2 do 20m2": (2, 1.5),
                "od 20 do 60m2": (3, 1.5),
                "powyżej 60m2": (4, 2.0)
            }
        }

    def pobierz_czas(self, przedzial):
        """Zwraca (pracownicy, czas_na_metr) dla danego przedziału."""
        for czas in self.czasy:
            if czas.przedzial == przedzial:
                return czas.pracownicy, czas.czas_na_metr
        return (1, 0.0)

    def ustaw_czasy(self, dane):
        """Ustawia czasy z słownika {przedzial: (pracownicy, czas)}."""
        MetodaCzas.query.filter_by(metoda_id=self.id).delete()
        for przedzial, (prac, czas) in dane.items():
            mc = MetodaCzas(
                metoda_id=self.id,
                przedzial=przedzial,
                pracownicy=prac,
                czas_na_metr=czas
            )
            db.session.add(mc)

class Grupa(db.Model):
    __tablename__ = 'grupa'
    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(100), unique=True, nullable=False)

    metody = db.relationship('Metoda', backref='grupa', cascade='all, delete-orphan')

    @staticmethod
    def domyslne_metody():
        return [
            "HF Duży (ZEMAT)",
            "HF Mały (WOLDAN)",
            "Gorące Powietrze (MILLER)",
            "Gorące Powietrze (Ręcznie)",
            "Gorące Powietrze (Zgrzewarka jezdna)",
            "Gorące Powietrze (ASATECH)",
            "Gorący Klin (SEAMTEC)"
        ]

class Obliczenie(db.Model):
    __tablename__ = 'obliczenie'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    kod = db.Column(db.String(20), nullable=False)
    grupa_id = db.Column(db.Integer, db.ForeignKey('grupa.id'))
    grupa = db.relationship('Grupa')
    przedzial = db.Column(db.String(50))
    czas_calkowity = db.Column(db.Float)
    wyniki_json = db.Column(db.Text)  # przechowuje JSON z wynikami szczegółowymi

    def wyniki(self):
        return json.loads(self.wyniki_json) if self.wyniki_json else []

    def zapisz_wyniki(self, wyniki_list):
        self.wyniki_json = json.dumps(wyniki_list, ensure_ascii=False)