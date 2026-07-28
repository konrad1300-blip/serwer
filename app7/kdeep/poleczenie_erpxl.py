import pandas as pd
import pyodbc

#-----------------------------------
# Działające połączenie z bazą ERPXL (Wersja dla Ubuntu / Linux)
#-----------------------------------

# 1. Definiowanie parametrów połączenia
server = "192.168.1.242"
database = "erpxl_hansaa"

# Tworzymy Connection String dopasowany pod sterownik Linuxowy msodbcsql17
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID=rkz;"
    f"PWD=hansaa2020;"
)

# 2. Twoje zapytanie SQL z poprawioną nazwą kolumny w nawiasach
sql_query = """
WITH CTE_RowNumber AS (
    SELECT DISTINCT
        PZL_ID,
        ZP,
        [DizałlZP],
        Prod_Kod,
        [Data aktywacji]
    FROM 
        CDN._IM_AM_plan_ciecia_gniazda
)
SELECT 
    PZL_ID,
    Prod_Kod,
    ZP,
    [DizałlZP],
    [Data aktywacji],
    ROW_NUMBER() OVER (PARTITION BY Prod_Kod ORDER BY PZL_ID) AS RowNumber
FROM 
    CTE_RowNumber;
"""

# 3. Nawiązanie połączenia i pobranie danych do Pandas DataFrame
def pobierz_dane_erpxl():
    with pyodbc.connect(conn_str) as conn:
        df = pd.read_sql(sql_query, conn)
    return df

# 4. Praca na pobranych danych (bezpiecznie, bez obciążania bazy)
if __name__ == '__main__':
    try:
        df = pobierz_dane_erpxl()
        if df is not None:
            print("Dane pobrane pomyślnie! Oto pierwsze 5 wierszy:")
            print(df.head())
    except Exception as e:
        print(f"Błąd podczas połączenia z ERPXL: {e}")
        df = None
