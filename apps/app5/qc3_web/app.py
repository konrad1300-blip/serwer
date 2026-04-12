import os
from flask import Flask, render_template, request
from database.db_handler import DatabaseHandler
from calculators.qc.routes import qc_bp
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.config.from_pyfile('config.py', silent=True)
app.config['SECRET_KEY'] = 'twoj-tajny-klucz-zmien-to-w-produkcji'
app.config['DATABASE'] = os.path.join(app.instance_path, 'reports.db')

# Dodaj obsługę proxy dla subkatalogu
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Wykryj prefix z nagłówka X-Forwarded-Prefix
@app.before_request
def set_url_prefix():
    if 'X-Forwarded-Prefix' in request.headers:
        request.environ['SCRIPT_NAME'] = request.headers['X-Forwarded-Prefix']

# Upewnij się, że katalog instance istnieje
os.makedirs(app.instance_path, exist_ok=True)

# Inicjalizacja bazy danych przy starcie
with app.app_context():
    db = DatabaseHandler(app.config['DATABASE'])
    db.initialize_database()

# Rejestracja blueprintów
app.register_blueprint(qc_bp, url_prefix='/qc')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5005)