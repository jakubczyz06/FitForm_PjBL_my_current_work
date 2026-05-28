import fitform_etl_users
import fitform_etl_daily_logs
import sys




def main():
    print("\n========================================")
    print("🚀 START GŁÓWNEGO POTOKU FITFORM ETL")
    print("========================================\n")

    # Krok 1. - Załadowanie użytkowników do tabeli 'users'
    print(">>> 1. Aktualizacja użytkowników (fitform_etl_users.py) <<<")
    try:
        fitform_etl_users.main()
        print("Krok 1. zakończony sukcesem.\n")

    except Exception as e:
        print(f"Krok 1. zakończony nieoczekiwanym błędem: {e}")
        sys.exit(1)

    # Krok 2. - Załadowanie danych dla każdego użytkownika do tabeli 'daily_logs'
    print(">>> 2. Wgrywanie logów dziennych (fitform_etl_daily_logs.py) <<<")
    try:
        fitform_etl_daily_logs.main()
        print("Krok 2. zakończony sukcesem.\n")

    except Exception as e:
        print(f"Krok 2. zakończony nieoczekiwanym błędem: {e}")
        sys.exit(1)

    print("========================================")
    print("🎉 WSZYSTKIE DANE PRZETWORZONE POMYŚLNIE")
    print("========================================\n")




if __name__ == '__main__':
    main()