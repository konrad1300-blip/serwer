import sqlite3
from flask import current_app

class DatabaseHandler:
    def __init__(self, db_path):
        self.db_path = db_path

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self.conn

    def disconnect(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def initialize_database(self):
        """Tworzy tabele, jeśli nie istnieją."""
        conn = self.connect()
        cursor = conn.cursor()

        # Tabela raportów (zgodna z oryginałem)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_number TEXT,
                report_date TEXT,
                reporter TEXT,
                shipping_direction TEXT,
                pallet_type TEXT,
                certified TEXT,
                pallet_size TEXT,
                pallet_length INTEGER,
                pallet_width INTEGER,
                pallet_height INTEGER,
                extensions INTEGER,
                stack_type TEXT,
                cartons INTEGER,
                products INTEGER,
                max_per_pallet INTEGER,
                unit_weight REAL,
                single_pallet_weight REAL,
                full_pallets INTEGER,
                remainder INTEGER,
                full_pallet_weight REAL,
                partial_pallet_weight REAL,
                total_weight_all REAL,
                pdf_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Dodaj brakujące kolumny (jeśli tabela już istniała)
        self._add_missing_columns()

        conn.commit()
        conn.close()

    def _add_missing_columns(self):
        """Dodaje brakujące kolumny do istniejącej tabeli."""
        cursor = self.cursor
        cursor.execute("PRAGMA table_info(reports)")
        existing = [col[1] for col in cursor.fetchall()]
        new_columns = [
            ('pallet_length', 'INTEGER'),
            ('pallet_width', 'INTEGER'),
            ('pallet_height', 'INTEGER'),
            ('products', 'INTEGER')
        ]
        for col_name, col_type in new_columns:
            if col_name not in existing:
                try:
                    cursor.execute(f'ALTER TABLE reports ADD COLUMN {col_name} {col_type}')
                except Exception as e:
                    print(f"Błąd przy dodawaniu kolumny {col_name}: {e}")

    def save_report(self, data):
        """Zapisuje raport do bazy, zwraca ID."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (
                product_number, report_date, reporter, shipping_direction,
                pallet_type, certified, pallet_size, pallet_length, pallet_width,
                pallet_height, extensions, stack_type, cartons, products,
                max_per_pallet, unit_weight, single_pallet_weight, full_pallets,
                remainder, full_pallet_weight, partial_pallet_weight, total_weight_all,
                pdf_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['product_number'], data['report_date'], data['reporter'],
            data['shipping_direction'], data['pallet_type'], data['certified'],
            data['pallet_size'], data['pallet_length'], data['pallet_width'],
            data['pallet_height'], data['extensions'], data['stack_type'],
            data['cartons'], data['products'], data['max_per_pallet'],
            data['unit_weight'], data['single_pallet_weight'], data['full_pallets'],
            data['remainder'], data['full_pallet_weight'], data['partial_pallet_weight'],
            data['total_weight_all'], data.get('pdf_path', '')
        ))
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return report_id

    def get_all_reports(self):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_reports_by_date_range(self, start_date, end_date):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reports
            WHERE date(created_at) BETWEEN ? AND ?
            ORDER BY created_at DESC
        ''', (start_date, end_date))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_reports_by_controller(self, controller):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reports
            WHERE reporter LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{controller}%',))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_reports_by_product(self, product):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reports
            WHERE product_number LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{product}%',))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_controllers(self):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT reporter FROM reports ORDER BY reporter')
        rows = [row[0] for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_products(self):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT product_number FROM reports ORDER BY product_number')
        rows = [row[0] for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_statistics(self, start_date=None, end_date=None):
        conn = self.connect()
        cursor = conn.cursor()
        if start_date and end_date:
            query = '''
                SELECT
                    COUNT(*) as total_reports,
                    SUM(cartons) as total_cartons,
                    SUM(full_pallets) as total_full_pallets,
                    SUM(total_weight_all) as total_weight,
                    reporter,
                    product_number
                FROM reports
                WHERE date(created_at) BETWEEN ? AND ?
                GROUP BY reporter, product_number
                ORDER BY total_reports DESC
            '''
            cursor.execute(query, (start_date, end_date))
        else:
            query = '''
                SELECT
                    COUNT(*) as total_reports,
                    SUM(cartons) as total_cartons,
                    SUM(full_pallets) as total_full_pallets,
                    SUM(total_weight_all) as total_weight,
                    reporter,
                    product_number
                FROM reports
                GROUP BY reporter, product_number
                ORDER BY total_reports DESC
            '''
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def delete_report(self, report_id):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reports WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()

    def get_report_by_id(self, report_id):
        """Pobiera pojedynczy raport po ID."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
        row = cursor.fetchone()
        conn.close()
        return row