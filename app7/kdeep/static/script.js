// static/script.js
// KIT-zen – obsługa powiadomień, toastów, prawego kliknięcia i dynamicznych interakcji

// Uruchom po załadowaniu DOM
document.addEventListener('DOMContentLoaded', function() {
    // ---- Powiadomienia ----
    const notificationBell = document.getElementById('notificationBell');
    const notifCounter = document.getElementById('notifCounter');

    // Pobierz i wyświetl nieprzeczytane powiadomienia
    function fetchNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                if (data.count > 0) {
                    if (notifCounter) {
                        notifCounter.style.display = 'inline-block';
                        notifCounter.innerText = data.count > 9 ? '9+' : data.count;
                    }
                    // Pokaż toasta dla najnowszego (lub wszystkich – ograniczamy do 1)
                    if (data.messages && data.messages.length > 0) {
                        showToast(data.messages[0].text, data.messages[0].id);
                    }
                } else {
                    if (notifCounter) notifCounter.style.display = 'none';
                }
            })
            .catch(err => console.warn('Błąd pobierania powiadomień:', err));
    }

    // Wyświetl toasta z możliwością zamknięcia (X lub prawy klik)
    function showToast(message, notifId) {
        // Usuń istniejące toasty (zapobiegaj nakładaniu)
        const existingToasts = document.querySelectorAll('.toast-notification');
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = 'toast-notification p-3';
        toast.setAttribute('data-id', notifId);
        toast.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span><i class="fas fa-info-circle text-primary me-2"></i> ${escapeHtml(message)}</span>
                <button type="button" class="btn-close btn-close-sm close-toast" data-id="${notifId}" aria-label="Zamknij"></button>
            </div>
        `;
        document.body.appendChild(toast);

        // Obsługa zamknięcia przez kliknięcie X
        const closeBtn = toast.querySelector('.close-toast');
        closeBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const id = this.getAttribute('data-id');
            markAsRead(id);
            toast.remove();
        });

        // Zamknięcie przez prawy przycisk myszy (contextmenu) – kluczowa funkcjonalność
        toast.addEventListener('contextmenu', function(e) {
            e.preventDefault();  // blokuje domyślne menu przeglądarki
            const id = this.getAttribute('data-id');
            markAsRead(id);
            this.remove();
        });

        // Auto-usunięcie po 10 sekundach
        setTimeout(() => {
            if (toast && toast.parentNode) {
                // nie oznaczaj jako przeczytane przy auto-usunięciu – tylko fizyczne usunięcie
                toast.remove();
            }
        }, 10000);
    }

    // Oznacz jako przeczytane (wywołanie API)
    function markAsRead(notifId) {
        fetch(`/api/mark_read/${notifId}`, { method: 'POST' })
            .then(() => {
                // po oznaczeniu odśwież licznik
                fetchNotifications();
            })
            .catch(err => console.warn('Błąd oznaczania jako przeczytane:', err));
    }

    // Dzwonek – pokaż listę nieprzeczytanych (alert zbiorczy)
    if (notificationBell) {
        notificationBell.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications')
                .then(res => res.json())
                .then(data => {
                    if (data.messages && data.messages.length) {
                        const list = data.messages.map(m => `• ${m.text}`).join('\n');
                        alert('Nieprzeczytane powiadomienia:\n' + list);
                    } else {
                        alert('Brak nowych powiadomień.');
                    }
                })
                .catch(() => alert('Nie udało się pobrać powiadomień.'));
        });
    }

    // ---- Automatyczne odświeżanie (polling) ----
    if (window.location.pathname !== '/login') {
        fetchNotifications();
        setInterval(fetchNotifications, 30000); // co 30 sekund
    }

    // ---- Pomocnicza funkcja do unikania XSS ----
    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        }).replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, function(c) {
            return c;
        });
    }

    // ---- Wizualizacja prostokąta czasu (opcjonalnie: aktualizacja szerokości) ----
    // Jeśli w projekcie używane są elementy z klasą .time-rectangle, przelicz szerokość na podstawie atrybutu data-hours
    function updateTimeRectangles() {
        document.querySelectorAll('.time-rectangle').forEach(el => {
            let hours = parseFloat(el.getAttribute('data-hours') || 1);
            // Maksymalna szerokość wizualna przyjmujemy 40h = 100% szerokości kontenera
            let percent = Math.min(100, (hours / 40) * 100);
            el.style.width = percent + '%';
            if (hours > 40) el.style.backgroundColor = '#ffc107'; // ostrzeżenie
        });
    }
    updateTimeRectangles();

    // Obsługa potwierdzeń przed usunięciem (dodatkowe zabezpieczenie)
    const deleteButtons = document.querySelectorAll('.btn-danger, .delete-confirm');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Czy na pewno chcesz usunąć? Operacja jest nieodwracalna.')) {
                e.preventDefault();
            }
        });
    });

    // Aktywne zaznaczanie linków w menu (opcjonalne)
    const currentPath = window.location.pathname;
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active', 'fw-bold');
            link.style.color = '#0d6efd';
        }
    });
});