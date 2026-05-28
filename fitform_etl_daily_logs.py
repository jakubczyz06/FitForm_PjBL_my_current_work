# Importy
import pandas as pd
import numpy as np
import logging
import zipfile
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
import os
import glob
import shutil
from dotenv import load_dotenv
import sys





# Załadowanie zmiennych środowiskowych z pliku .env
load_dotenv()




# Konfiguracja logger'a
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'daily_logs_etl.log')

logger = logging.getLogger('daily_logs_etl')
logger.setLevel(logging.INFO)

# Zabezpieczenie przed dublowaniem wpisów
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, mode = 'a', encoding = 'utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt = "%Y-%m-%d %H:%M")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)




# Pobieranie numeru ID użytkowników z bazy danych
def get_user_mapping(engine):
    logging.info('---POBIERANIE LISTY UŻYTKOWNIKÓW Z BAZY DLA "DAILY_LOGS"---')

    try:
        query = "SELECT user_id, name FROM users;"
        df_users = pd.read_sql(query, engine)

        # Tworzenie słownika: {'user_id': 'name'}
        user_dict = dict(zip(df_users['user_id'], df_users['name']))
        return user_dict


    except Exception as e:
        logging.error(f'---BŁĄD PODCZAS POBIERANIA LISTY UŻYTKOWNIKÓW: {e}---')
        return {}





# E - Wczytywanie pliku .CSV z danymi badanych z pliku .ZIP
def extract_data(zip_file):
    logging.info(f'---EKSTRAKCJA DANYCH Z PLIKU {zip_file}---')
    wyniki = {}

    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            for file_name in zf.namelist():
                if file_name.endswith('.csv'):
                    logging.info(f'---PRZETWARZANIE PLIKU {file_name} DLA "DAILY_LOGS"---')
                    with zf.open(file_name) as f:
                        df_part = pd.read_csv(f, sep = ',', encoding = 'utf-8-sig')
                        wyniki[file_name] = df_part
                    logging.info(f'---POMYŚLNIE WCZYTANO {len(df_part)} WIERSZY Z PLIKU {file_name}"---')

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

    logging.info('---ROZPOCZĘCIE TRANSFORMACJI DANYCH DLA "DAILY_LOGS"---')

    # Upewnienie się, czy ekstrakcja danych na pewno coś zwróciła
    if df is None or df.empty:
        logging.warning('---BRAK DANYCH DO TRANSFORMACJI, PRZERYWANIE OPERACJI"---')
        return None

    try:
        # Otrzymano DataFrame
        logging.info(f'---OTRZYMANO DATAFRAME: {df.shape[0]} WIERSZY, {df.shape[1]} KOLUMN---')

        # Mapowanie nazw kolumn
        column_mapping = {
            'Data': 'data_wpisu',
            'Zjedzone kcal': 'zjedzone_kcal',
            'Białko (w gramach)': 'bialko_g',
            'Spalone kcal': 'spalone_kcal',
            'Długość aktywności typu cardio': 'cardio_min',
            'Trening siłowy (tak/nie)': 'trening_silowy',
            'Ile kroków': 'kroki',
            'Waga na czczo': 'waga_czczo',
            'Płeć': 'plec'
        }
        df.rename(columns = column_mapping, inplace = True)

        # Przypisanie ID użytkownika
        df['user_id'] = user_id

        # Usunięcie kolumny 'płeć' (jest ona brana pod uwagę w innym projektowym pipeline ETL)
        if 'plec' in df.columns:
            df.drop(columns = ['plec'], inplace = True)


        # Konwersja i czyszczenie danych
        # 1. Ustawienie daty wpisu do oczekiwanego zapisu
        df['data_wpisu'] = pd.to_datetime(df['data_wpisu'], format = 'mixed', errors = 'coerce').dt.date

        # 2. Zamiana str na int w kolumnie 'trening_silowy'
        if 'trening_silowy' in df.columns:
            df['trening_silowy'] = np.where(df['trening_silowy'].astype(str).str.strip().str.lower() == 'tak', 1, 0)

        # 3. Konwersje danych numerycznych
        numeric_columns = ['zjedzone_kcal', 'bialko_g', 'spalone_kcal', 'cardio_min', 'kroki', 'waga_czczo']
        for column in numeric_columns:
            if column in df.columns:
                df[column] = df[column].astype(str).str.replace(' ', '').str.replace(',', '.')
                df[column] = pd.to_numeric(df[column], errors='coerce')
                df[column] = df[column].str.replace(r'[^\d.]', '', regex = True)

        cols_to_zero = ['zjedzone_kcal', 'spalone_kcal', 'cardio_min', 'kroki', 'bialko_g']
        for column in cols_to_zero:
            if column in df.columns:
                df[column] = df[column].fillna(0)

        # 4. Walidacja zakresu wagi
        if 'waga_czczo' in df.columns:
            df = df[df['waga_czczo'].isna() | df['waga_czczo'].between(30, 635)]

        # 5. Zabezpieczenie Compound Key
        df.dropna(subset = ['data_wpisu'], inplace = True)
        df.drop_duplicates(subset = ['user_id', 'data_wpisu'], keep = 'last', inplace = True)
        df = df.replace({np.nan: None})

        logging.info(f'---TRANSFORMACJA DLA "DAILY_LOGS" ZAKOŃCZONA SUKCESEM.'
                     f' LICZBA GOTOWYCH WIERSZY: {df.shape[0]}---')

        return df

    except Exception as e:
        logging.error(f'---WYSTĄPIŁ NIEOCZEKIWANY BŁĄD PODCZAS TRANSFORMACJI: {e}---')
        return None




# L - Wczytanie danych do bazy danych 'FitForm' w chmurze
def load_data(df, table_name, engine):

    logging.info('---WCZYTYWANIE DANYCH DLA "DAILY_LOGS" DO BAZY---')

    if df is None or df.empty:
        logging.warning('---BRAK DANYCH DO WCZYTANIA DO BAZY, PRZERYWANIE OPERACJI---')
        return False

    try:
        def insert_on_conflict(table, conn, keys, data_iter):
            data = [dict(zip(keys, row)) for row in data_iter]
            stmt = insert(table.table).values(data)
            update_dict = {c.name: c for c in stmt.excluded if c.name not in ['user_id', 'data_wpisu']}

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements = ['user_id', 'data_wpisu'],
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
                     f' {rows_imported} WIERSZY W TABELI "{table_name}" DLA "DAILY_LOGS"---')
        return True


    except Exception as e:
        logging.error(f'---KRYTYCZNY BŁĄD PODCZAS WCZYTYWANIA DANYCH DO SQL: {e}---')
        return False





def main():
    logging.info('---START PROCESU ETL DLA "DAILY_LOGS"---')

    # Pobranie adresu z pliku .env
    db_url = os.getenv('FITFORM_DB_URL')
    if not db_url:
        logging.error('---BŁĄD: BRAK ZMIENNEJ ŚRODOWISKOWEJ FITFORM_DB_URL. SPRAWDŹ PLIK .ENV---')
        sys.exit(1)

    # Zrobienie połączenia z bazą danych z URL
    engine = create_engine(db_url)

    user_mapping = get_user_mapping(engine)
    if not user_mapping:
        logging.error('---SŁOWNIK PUSTY. PRZERYWANIE PROCESU---')
        sys.exit(1)

    docelowa_tabela = 'daily_logs'

    # Archiwizacja plików dodanych do bazy danych
    katalog_danych = 'dane_uzytkownikow'
    katalog_archiwum = os.path.join(katalog_danych, 'archiwum')
    os.makedirs(katalog_archiwum, exist_ok = True)

    # Otwieranie plików CSV i wywołanie funkcji 'extract_data'
    sciezka_do_plikow = os.path.join(katalog_danych, '*.zip')
    lista_plikow_zip = glob.glob(sciezka_do_plikow)

    logging.info(f'---ZNALEZIONO {len(lista_plikow_zip)} PLIKÓW DO PRZETWORZENIA---')

    for plik in lista_plikow_zip:
        nazwa_zip = os.path.basename(plik)
        logging.info(f'---OTWIERANIE PACZKI ZIP: {nazwa_zip}---')

        try:
            pliki_csv = extract_data(plik)

            for nazwa_csv, dane_df in pliki_csv.items():
                try:
                    id_z_pliku = int(nazwa_csv.split('_')[0])

                    if id_z_pliku not in user_mapping:
                        logging.error(f'---BŁĄD: NIE MA UŻYTKOWNIKA O ID {id_z_pliku} W BAZIE---')
                        continue

                    imie_z_bazy = user_mapping[id_z_pliku]
                    logging.info(f'---PRZETWARZANIE: {nazwa_csv} (USER: {imie_z_bazy}, ID: {id_z_pliku})---')

                    czysty_df = transform_data(dane_df, user_id = id_z_pliku)

                    if czysty_df is not None:
                        load_data(czysty_df, docelowa_tabela, engine)

                except (ValueError, IndexError):
                    logging.warning(f"---POMINIĘTO: {nazwa_csv} (BRAK ID W NAZWIE)---")

            sciezka_docelowa = os.path.join(katalog_archiwum, nazwa_zip)
            shutil.move(plik, sciezka_docelowa)


        except Exception as e:
            logging.error(f"---BŁĄD PODCZAS PRZETWARZANIA PACZKI {nazwa_zip}: {e}---")

    # Sukces, pomyślny koniec procesu
    logging.info('---ZAKOŃCZONO PROCES ETL "DAILY_LOGS"---')

    engine.dispose()
    logging.info('---ZAMKNIĘTO POŁĄCZENIE Z BAZĄ---')




# Blokada samodzielnego uruchomienia skryptu, co mogłoby zepsuć wczytywanie danych do bazy
if __name__ == '__main__':
    print("!!! Tego skryptu nie należy uruchamiać samodzielnie !!!")
    print("!!! Aby uruchomić proces ETL, użyj pliku: 'run_pipeline.py' !!!")
    sys.exit(1)