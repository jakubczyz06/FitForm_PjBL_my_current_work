# Importy
import pandas as pd
import logging
import zipfile
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
import os
import glob
from dotenv import load_dotenv
import sys
from unidecode import unidecode




# Załadowanie zmiennych środowiskowych z pliku .env
load_dotenv()




# Konfiguracja logger'a
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users_etl.log')

logger = logging.getLogger('users_etl')
logger.setLevel(logging.INFO)

# Zabezpieczenie przed dublowaniem wpisów
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, mode = 'a', encoding = 'utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt = "%Y-%m-%d %H:%M")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)




# E - Wczytywanie pliku .CSV z danymi badanych z pliku .ZIP
def extract_data(zip_file):
    logging.info(f'---EKSTRAKCJA DANYCH Z PLIKU {zip_file}---')
    wyniki = {}

    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            for file_name in zf.namelist():
                if file_name.endswith('.csv'):
                    logging.info(f'---PRZETWARZANIE PLIKU {file_name} DLA "USERS"---')
                    with zf.open(file_name) as f:
                        df_part = pd.read_csv(f, sep = ',', encoding = 'utf-8-sig')
                        wyniki[file_name] = df_part
                    logging.info(f'---POMYŚLNIE WCZYTANO {len(df_part)} WIERSZY Z PLIKU {file_name}---')

        if not wyniki:
            logging.warning(f'---BRAK PLIKÓW .CSV W ARCHIWUM {zip_file}---')

        return wyniki

    except FileNotFoundError:
        logging.error(f'---BŁĄD: BRAK PLIKU {zip_file}---')
        return {}
    except zipfile.BadZipFile:
        logging.error(f'---BŁĄD: PLIK {zip_file} JEST USZKODZONY BĄDŹ NIEPOPRAWNY---')
        return {}
    except Exception as e:
        logging.error(f'---WYSTĄPIŁ NIEOCZEKIWANY BŁĄD PODCZAS EKSTRAKCJI: {e}---')
        return {}




# T - Transformacja surowych danych przy użyciu Pandas i NumPy
def transform_data(df, user_id):

    logging.info('---ROZPOCZĘCIE TRANSFORMACJI DANYCH DLA "USERS"---')

    # Upewnienie się, czy ekstrakcja danych na pewno coś zwróciła
    if df is None or df.empty:
        logging.warning('---BRAK DANYCH DO TRANSFORMACJI, PRZERYWANIE OPERACJI---')
        return None

    try:
        # Otrzymano DataFrame
        logging.info(f'---OTRZYMANO DATAFRAME: {df.shape[0]} WIERSZY, {df.shape[1]} KOLUMN---')

        # Pozostawienie jedynie kolumny "Płeć", gdyż tylko ona nas interesuje
        df = df[['Płeć']]
        df.rename(columns = {'Płeć': 'plec'}, inplace = True)

        # Przypisanie ID użytkownika
        df['user_id'] = user_id

        # Konwersja i czyszczenie danych
        # 1. Oczyszczenie kolumny płeć oraz wybór najczęściej powtarzanej się płci
        df['plec'] = (
                    df['plec']
                    .str.replace(' ', '', regex=False)
                    .str.lower()
                    .apply(lambda x: unidecode(x) if pd.notna(x) else x)
                    )

        if not df['plec'].dropna().empty:
            plec = df['plec'].mode()[0]
        else:
            plec = '-'

        if plec in ('mezczyzna', 'm'):
            plec = 'M'
        elif plec in ('kobieta', 'k'):
            plec = 'K'
        else:
            plec = '-'

        # 2. Automatyczne nadanie 'name' użytkownikowi
        wygenerowane_imie = f"User{user_id}"

        df = pd.DataFrame({
            'user_id': [user_id],
            'name': [wygenerowane_imie],
            'plec': [plec]
        })

        logging.info(f'---TRANSFORMACJA DLA "USERS" ZAKOŃCZONA SUKCESEM.'
                     f' LICZBA GOTOWYCH WIERSZY: {df.shape[0]}---')

        return df

    except Exception as e:
        logging.error(f'---WYSTĄPIŁ NIEOCZEKIWANY BŁĄD PODCZAS TRANSFORMACJI: {e}---')
        return None




# L - Wczytanie danych do bazy danych 'FitForm' w chmurze
def load_data(df, table_name, engine):

    logging.info('---WCZYTYWANIE DANYCH DLA "USERS" DO BAZY---')

    if df is None or df.empty:
        logging.warning('---BRAK DANYCH DO WCZYTANIA DO BAZY, PRZERYWANIE OPERACJI---')
        return False

    try:
        def insert_on_conflict(table, conn, keys, data_iter):
            data = [dict(zip(keys, row)) for row in data_iter]
            stmt = insert(table.table).values(data)
            update_dict = {c.name: c for c in stmt.excluded if c.name not in ['user_id', 'name']}

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements = ['user_id'],
                set_ = update_dict
            )
            conn.execute(upsert_stmt)

        # Wypychanie danych z Pandasa do bazy
        df.to_sql(
            name = table_name,
            con = engine,
            if_exists = 'append',  # Dodanie do istniejącej tabeli
            index = False,  # Upewnienie się o braku wgrywania wewnętrznego indeksu Pandasa (0, 1, 2...)
            method = insert_on_conflict  # Użycie funkcji UPSERT
        )

        rows_imported = len(df)
        logging.info(f'---SUKCES! WCZYTANO, BĄDŹ ZAKTUALIZOWANO'
                     f' {rows_imported} WIERSZY W TABELI "{table_name}" DLA "USERS"---')
        return True

    except Exception as e:
        logging.error(f'---KRYTYCZNY BŁĄD PODCZAS WCZYTYWANIA DANYCH DO SQL: {e}---')
        return False




def main():
    logging.info('---START PROCESU ETL DLA "USERS"---')

    # Pobranie adresu z pliku .env
    db_url = os.getenv('FITFORM_DB_URL')
    if not db_url:
        logging.error('---BŁĄD: BRAK ZMIENNEJ ŚRODOWISKOWEJ FITFORM_DB_URL. SPRAWDŹ PLIK .ENV---')
        sys.exit(1)

    # Zrobienie połączenia z bazą danych z URL
    engine = create_engine(db_url)
    docelowa_tabela = 'users'

    # Wczytanie danych z pliku .ZIP
    katalog_danych = 'dane_uzytkownikow'
    sciezka_do_plikow = os.path.join(katalog_danych, '*.zip')
    lista_plikow_zip = glob.glob(sciezka_do_plikow)

    logging.info(f'---ZNALEZIONO {len(lista_plikow_zip)} PLIKÓW DO PRZETWORZENIA---')

    # Proces ETL
    for plik in lista_plikow_zip:
        nazwa_zip = os.path.basename(plik)
        logging.info(f'---OTWIERANIE PACZKI ZIP: {nazwa_zip}---')

        try:
            pliki_csv = extract_data(plik)

            for nazwa_csv, dane_df in pliki_csv.items():
                try:
                    id_z_pliku = int(nazwa_csv.split('_')[0])

                    czysty_df = transform_data(dane_df, user_id = id_z_pliku)

                    if czysty_df is not None:
                        load_data(czysty_df, docelowa_tabela, engine)

                except (ValueError, IndexError):
                    logging.warning(f"---POMINIĘTO: {nazwa_csv}---")


        except Exception as e:
            logging.error(f"---BŁĄD PODCZAS PRZETWARZANIA PACZKI {nazwa_zip}: {e}---")

    # Sukces, pomyślny koniec procesu
    logging.info('---ZAKOŃCZONO PROCES ETL DLA "USERS"---')

    engine.dispose()
    logging.info('---ZAMKNIĘTO POŁĄCZENIE Z BAZĄ---')




# Blokada samodzielnego uruchomienia skryptu, co mogłoby zepsuć wczytywanie danych do bazy
if __name__ == '__main__':
    print("!!! Tego skryptu nie należy uruchamiać samodzielnie !!!")
    print("!!! Aby uruchomić proces ETL, użyj pliku: 'run_pipeline.py' !!!")
    sys.exit(1)