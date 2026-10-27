"""
Produkcyjny entry point dla AcceptaDoc.

Różnice względem `app.py`:
  - NIE uruchamia serwera deweloperskiego Flaska (`app.run`).
  - Używa WSGI serwera Waitress (produkcyjny, wielowątkowy).
  - Włącza ProxyFix, żeby aplikacja poprawnie działała pod subścieżką
    (np. /app11) za Apache reverse proxy.

Uruchomienie (ręcznie):
    python run_prod.py

Uruchomienie (produkcyjnie, przez systemd):
    sudo systemctl start app11
"""

import os
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

from app import app  # import naszej aplikacji Flask


# ── Konfiguracja ──────────────────────────────────────────────────────────────
HOST = '127.0.0.1'
PORT = 5011
THREADS = 8  # liczba równoległych wątków obsługi; dla 10-30 userów spokojnie wystarczy


# ── ProxyFix ──────────────────────────────────────────────────────────────────
# Dlaczego to jest konieczne pod Apache z subścieżką /app11:
#   Apache ustawia nagłówek X-Forwarded-Prefix: /app11.
#   Bez ProxyFix Flask nie wie, że działa pod prefiksem, więc:
#     - url_for() generuje linki bez /app11 → przekierowania na złą stronę,
#     - pliki statyczne (/static/...) lecą bez /app11 → 404 → brak CSS/JS,
#     - formularze POST trafiają w zły URL → 404.
# ProxyFix czyta nagłówki X-Forwarded-* i koryguje wewnętrzny widok requestu.
# x_prefix=1 → bierze X-Forwarded-Prefix (nasz /app11).
# x_proto=1  → bierze X-Forwarded-Proto (http/https) – ważne przy redirectach.
# x_host=1   → bierze X-Forwarded-Host (nazwa hosta z zewnątrz).
# x_for=1    → bierze X-Forwarded-For (IP klienta do logów).
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1,
)


# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Upewniamy się, że baza istnieje (Waitress nie odpala __main__ z app.py)
    from db import init_db
    with app.app_context():
        init_db()

    print(f'[run_prod] AcceptaDoc startuje pod {HOST}:{PORT} (threads={THREADS})')
    serve(app, host=HOST, port=PORT, threads=THREADS)