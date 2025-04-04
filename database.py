# Plik: database.py

import sqlite3
import os
from datetime import date, timedelta, datetime

# Nazwa pliku bazy danych
DATABASE_FILENAME = 'game_database.db'
# Ścieżka do pliku schema.sql (zakładamy, że jest w tym samym folderze co database.py)
SCHEMA_FILENAME = 'schema.sql'

def get_db_connection():
    """Tworzy i zwraca połączenie z bazą danych."""
    # Sprawdź, czy plik bazy istnieje, jeśli nie, init_db go utworzy
    should_initialize = not os.path.exists(DATABASE_FILENAME)
    conn = sqlite3.connect(DATABASE_FILENAME)
    # Używaj obiektów Row, które działają jak słowniki (dostęp przez nazwę kolumny)
    conn.row_factory = sqlite3.Row

    if should_initialize:
        print(f"Plik bazy danych '{DATABASE_FILENAME}' nie znaleziony. Inicjalizuję...")
        _init_db(conn) # Używamy prywatnej funkcji z istniejącym połączeniem
        print("Inicjalizacja bazy danych zakończona.")

    return conn

def _init_db(connection):
    """
    Inicjalizuje bazę danych, wykonując skrypt SQL ze schema.sql.
    Używa istniejącego połączenia.
    """
    print(f"Odczytuję schemat z pliku: {SCHEMA_FILENAME}")
    try:
        with open(SCHEMA_FILENAME, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        print("Wykonywanie skryptu SQL...")
        connection.executescript(sql_script)
        connection.commit()
        print("Schemat bazy danych został utworzony/zaktualizowany.")
    except FileNotFoundError:
        print(f"BŁĄD: Nie znaleziono pliku schematu '{SCHEMA_FILENAME}'.")
    except sqlite3.Error as e:
        print(f"BŁĄD podczas inicjalizacji bazy danych: {e}")
        # Rozważ rzucenie wyjątku dalej, jeśli to krytyczny błąd
        # raise

# --- Funkcje dla tabeli 'words' ---

def add_word(word, hint, syllables_str):
    """Dodaje nowe słowo do bazy. Zwraca ID dodanego słowa lub None w przypadku błędu."""
    conn = get_db_connection()
    try:
        with conn: # Użycie 'with conn' automatycznie zarządza transakcjami (commit/rollback)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO words (word, hint, syllables) VALUES (?, ?, ?)",
                (word, hint, syllables_str)
            )
            print(f"Dodano słowo: {word}")
            return cursor.lastrowid # Zwraca ID ostatnio wstawionego wiersza
    except sqlite3.IntegrityError:
        print(f"BŁĄD: Słowo '{word}' już istnieje w bazie danych.")
        return None
    except sqlite3.Error as e:
        print(f"BŁĄD podczas dodawania słowa: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_words_for_puzzle(count=5, exclude_used_within_days=30):
    """
    Pobiera 'count' losowych słów, które nie były używane przez ostatnie
    'exclude_used_within_days' dni. Zwraca listę obiektów Row.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Oblicz datę graniczną
        cutoff_date = date.today() - timedelta(days=exclude_used_within_days)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')

        # Wybierz losowe słowa spełniające kryteria daty
        cursor.execute(
            """
            SELECT id, word, hint, syllables
            FROM words
            WHERE last_used_date IS NULL OR last_used_date <= ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (cutoff_date_str, count)
        )
        words = cursor.fetchall() # Pobierz wszystkie pasujące wiersze
        print(f"Pobrano {len(words)} słów do zagadki.")
        if len(words) < count:
            print(f"OSTRZEŻENIE: Nie znaleziono wystarczającej liczby ({count}) nieużywanych słów. Znaleziono: {len(words)}.")
            # Można dodać logikę awaryjną, np. pobrać najdawniej używane, jeśli potrzeba
        return words
    except sqlite3.Error as e:
        print(f"BŁĄD podczas pobierania słów do zagadki: {e}")
        return [] # Zwróć pustą listę w przypadku błędu
    finally:
        if conn:
            conn.close()

def get_word_details(word_ids_list):
    """Pobiera szczegóły słów (word, hint, syllables) na podstawie listy ID."""
    if not word_ids_list:
        return []
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Tworzymy listę placeholderów (?) na podstawie liczby ID
        placeholders = ', '.join('?' for _ in word_ids_list)
        query = f"SELECT id, word, hint, syllables FROM words WHERE id IN ({placeholders})"
        cursor.execute(query, word_ids_list)
        words = cursor.fetchall()
        # Opcjonalnie: Posortuj wyniki, aby pasowały do kolejności ID wejściowych
        word_map = {row['id']: row for row in words}
        sorted_words = [word_map.get(id) for id in word_ids_list if word_map.get(id)]
        return sorted_words
    except sqlite3.Error as e:
        print(f"BŁĄD podczas pobierania szczegółów słów: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_last_used_date(word_ids_list, puzzle_date):
    """Aktualizuje datę ostatniego użycia dla podanych ID słów."""
    if not word_ids_list:
        return False
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            puzzle_date_str = puzzle_date.strftime('%Y-%m-%d')
            placeholders = ', '.join('?' for _ in word_ids_list)
            query = f"UPDATE words SET last_used_date = ? WHERE id IN ({placeholders})"
            # Pierwszy parametr to data, reszta to ID
            params = [puzzle_date_str] + word_ids_list
            cursor.execute(query, params)
            print(f"Zaktualizowano last_used_date dla {cursor.rowcount} słów na {puzzle_date_str}.")
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"BŁĄD podczas aktualizacji last_used_date: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- Funkcje dla tabeli 'daily_puzzles' ---

def get_daily_puzzle(puzzle_date):
    """Pobiera ID słów (jako string) dla zagadki z podanej daty."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        puzzle_date_str = puzzle_date.strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT word_ids FROM daily_puzzles WHERE puzzle_date = ?",
            (puzzle_date_str,)
        )
        result = cursor.fetchone() # Pobierz jeden wiersz
        if result:
            print(f"Znaleziono zagadkę dnia dla {puzzle_date_str}.")
            return result['word_ids'] # Zwraca string np. "1,5,23"
        else:
            print(f"Nie znaleziono zagadki dnia dla {puzzle_date_str}.")
            return None
    except sqlite3.Error as e:
        print(f"BŁĄD podczas pobierania zagadki dnia: {e}")
        return None
    finally:
        if conn:
            conn.close()

def save_daily_puzzle(puzzle_date, word_ids_list):
    """Zapisuje ID słów (konwertowane na string) dla zagadki z podanej daty."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            puzzle_date_str = puzzle_date.strftime('%Y-%m-%d')
            word_ids_str = ','.join(map(str, word_ids_list)) # Konwersja listy [1, 5, 23] na "1,5,23"
            # Używamy INSERT OR REPLACE, aby nadpisać istniejącą zagadkę dla tej daty, jeśli istnieje
            cursor.execute(
                "INSERT OR REPLACE INTO daily_puzzles (puzzle_date, word_ids) VALUES (?, ?)",
                (puzzle_date_str, word_ids_str)
            )
            print(f"Zapisano zagadkę dnia dla {puzzle_date_str} z ID słów: {word_ids_str}.")
            return True
    except sqlite3.Error as e:
        print(f"BŁĄD podczas zapisywania zagadki dnia: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- Funkcje dla tabeli 'scores' ---

def save_score(puzzle_date, nickname, time_seconds):
    """Zapisuje wynik gracza dla zagadki z podanej daty."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            puzzle_date_str = puzzle_date.strftime('%Y-%m-%d')
            cursor.execute(
                "INSERT INTO scores (puzzle_date, nickname, time_seconds) VALUES (?, ?, ?)",
                (puzzle_date_str, nickname, time_seconds)
            )
            print(f"Zapisano wynik dla '{nickname}' ({time_seconds}s) w dniu {puzzle_date_str}.")
            return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"BŁĄD podczas zapisywania wyniku: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_daily_scores(puzzle_date, limit=10):
    """Pobiera najlepsze 'limit' wyników dla zagadki z podanej daty, posortowane wg czasu."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        puzzle_date_str = puzzle_date.strftime('%Y-%m-%d')
        cursor.execute(
            """
            SELECT nickname, time_seconds
            FROM scores
            WHERE puzzle_date = ?
            ORDER BY time_seconds ASC -- Najlepsze (najkrótsze) czasy na górze
            LIMIT ?
            """,
            (puzzle_date_str, limit)
        )
        scores = cursor.fetchall()
        print(f"Pobrano {len(scores)} najlepszych wyników dla {puzzle_date_str}.")
        return scores
    except sqlite3.Error as e:
        print(f"BŁĄD podczas pobierania wyników dnia: {e}")
        return []
    finally:
        if conn:
            conn.close()


# --- Funkcja do dodawania słów z pliku (opcjonalnie) ---
def populate_words_from_file(filename="words_data.py"):
    """Wczytuje słowa z pliku i dodaje je do bazy danych."""
    try:
        # Prosty sposób na wczytanie danych, jeśli są w formacie listy tupli w pliku .py
        # UWAGA: exec jest potencjalnie niebezpieczny, jeśli plik pochodzi z niezaufanego źródła!
        # Lepszym rozwiązaniem byłby format CSV lub JSON.
        with open(filename, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Zakładamy, że plik definiuje listę o nazwie `initial_words`
        # Przykład zawartości words_data.py:
        # initial_words = [
        #     ('jabłko', 'Owoc z drzewa', 'jabł-ko'),
        #     ('zagadka', 'Łamigłówka', 'za-gad-ka'),
        #     # ... więcej słów
        # ]
        local_namespace = {}
        exec(file_content, {}, local_namespace) 
        
        if 'initial_words' in local_namespace:
            words_to_add = local_namespace['initial_words']
            print(f"Znaleziono {len(words_to_add)} słów w pliku '{filename}'. Dodawanie do bazy...")
            added_count = 0
            for word, hint, syllables in words_to_add:
                if add_word(word, hint, syllables):
                    added_count += 1
            print(f"Dodano {added_count} nowych słów.")
        else:
            print(f"OSTRZEŻENIE: Nie znaleziono listy 'initial_words' w pliku '{filename}'.")

    except FileNotFoundError:
        print(f"OSTRZEŻENIE: Plik z danymi słów '{filename}' nie znaleziony.")
    except Exception as e:
        print(f"BŁĄD podczas wczytywania słów z pliku '{filename}': {e}")


# --- Główna część skryptu (do testowania lub jednorazowej inicjalizacji) ---
if __name__ == '__main__':
    print("Uruchomiono database.py bezpośrednio.")
    
    # 1. Inicjalizacja bazy danych (jeśli plik nie istnieje, zostanie utworzony)
    print("Test połączenia i inicjalizacji...")
    conn = get_db_connection() 
    conn.close() # Zamknij połączenie testowe
    print("-" * 20)

    # 2. Dodaj kilka przykładowych słów (jeśli ich jeszcze nie ma)
    # Możesz to zakomentować po pierwszym uruchomieniu lub użyć populate_words_from_file
    print("Dodawanie przykładowych słów (jeśli ich nie ma)...")
    add_word('testowy', 'Przykładowy wpis', 'tes-to-wy')
    add_word('program', 'Aplikacja komputerowa', 'pro-gram')
    add_word('sylaba', 'Część wyrazu', 'sy-la-ba')
    add_word('gra', 'Rozrywka', 'gra')
    add_word('język', 'Mowa lub część ciała', 'ję-zyk')
    add_word('python', 'Wąż lub język programowania', 'py-thon')
    add_word('łatwy', 'Nieskomplikowany', 'łat-wy')
    print("-" * 20)

    # Opcjonalnie: Wypełnij bazę z pliku words_data.py
    # print("Wypełnianie bazy z pliku words_data.py...")
    # populate_words_from_file("words_data.py") 
    # print("-" * 20)


    # 3. Przetestuj pobieranie słów do zagadki
    print("Test pobierania słów do zagadki...")
    puzzle_words = get_words_for_puzzle(count=5, exclude_used_within_days=1) # Krótki czas dla testu
    if puzzle_words:
        print(f"Wylosowane słowa ({len(puzzle_words)}):")
        for word_row in puzzle_words:
            print(f"  ID: {word_row['id']}, Słowo: {word_row['word']}, Podpowiedź: {word_row['hint']}, Sylaby: {word_row['syllables']}")
        
        # 4. Przetestuj aktualizację daty użycia
        print("\nTest aktualizacji daty użycia...")
        word_ids = [row['id'] for row in puzzle_words]
        today = date.today()
        update_last_used_date(word_ids, today)

# Sprawdź, czy data została zaktualizowana (przykładowe sprawdzenie dla pierwszego słowa)
        details = get_word_details([word_ids[0]])
        if details:
            # Po prostu sprawdźmy, czy dostaliśmy z powrotem dane dla tego ID
            print(f"Sprawdzenie pobrania szczegółów dla ID {word_ids[0]}: Słowo - {details[0]['word']}")
            # Wiemy, że update_last_used_date zostało wywołane wcześniej
            print(f"Data 'last_used_date' dla ID {word_ids[0]} została zaktualizowana w bazie (nie pobrano jej w tym zapytaniu).")
        else:
             print(f"Nie udało się pobrać szczegółów dla ID {word_ids[0]} po aktualizacji.")

    # 5. Przetestuj zapisywanie i pobieranie zagadki dnia
    print("Test zapisywania i pobierania zagadki dnia...")
    today = date.today()
    test_ids = [1, 2, 3] # Przykładowe ID (upewnij się, że istnieją w bazie)
    if save_daily_puzzle(today, test_ids):
        retrieved_ids_str = get_daily_puzzle(today)
        print(f"Pobrane ID dla dzisiaj: {retrieved_ids_str}")
        # Przetestuj pobranie dla innego dnia (powinno zwrócić None)
        yesterday = today - timedelta(days=1)
        print(f"Pobieranie dla wczoraj: {get_daily_puzzle(yesterday)}")
    print("-" * 20)

    # 6. Przetestuj zapisywanie i pobieranie wyników
    print("Test zapisywania i pobierania wyników...")
    save_score(today, "Tester1", 120)
    save_score(today, "Tester2", 95)
    save_score(today, "Tester1", 110) # Ten sam gracz, inny wynik
    save_score(yesterday, "Tester3", 150) # Wynik z wczoraj

    print("\nNajlepsze wyniki na dzisiaj:")
    scores_today = get_daily_scores(today, limit=5)
    if scores_today:
        for score in scores_today:
            print(f"  Gracz: {score['nickname']}, Czas: {score['time_seconds']}s")
    else:
        print("  Brak wyników na dzisiaj.")

    print("\nNajlepsze wyniki na wczoraj:")
    scores_yesterday = get_daily_scores(yesterday, limit=5)
    if scores_yesterday:
         for score in scores_yesterday:
            print(f"  Gracz: {score['nickname']}, Czas: {score['time_seconds']}s")
    else:
        print("  Brak wyników na wczoraj.")

    print("-" * 20)
    print("Zakończono testowanie database.py")