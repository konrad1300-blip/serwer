from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes.groups import bp as groups_bp
    from app.routes.methods import bp as methods_bp
    from app.routes.calculation import bp as calculation_bp

    app.register_blueprint(groups_bp, url_prefix='/grupy')
    app.register_blueprint(methods_bp, url_prefix='/metody')
    app.register_blueprint(calculation_bp, url_prefix='/obliczenia')

    @app.route('/')
    def index():
        return redirect(url_for('calculation.index'))

    with app.app_context():
        db.create_all()

    return app