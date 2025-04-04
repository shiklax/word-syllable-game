# Plik: app.py

from flask import Flask, jsonify, render_template, request
import database  # Importujemy nasz moduł do obsługi bazy danych
from datetime import date
import random

# Inicjalizacja aplikacji Flask
# Flask automatycznie szuka folderów 'templates' i 'static' na tym samym poziomie co ten plik
app = Flask(__name__)

# --- Główny widok aplikacji (serwuje plik HTML) ---
@app.route('/')
def index():
    """Serwuje główny plik HTML gry."""
    # Na razie tylko renderuje pusty szablon,
    # JavaScript w przeglądarce pobierze dane gry z API
    # Zakładamy, że masz folder 'templates' i w nim 'index.html'
    # Jeśli nie, stwórz pusty plik templates/index.html na razie
    try:
        return render_template('index.html')
    except Exception as e:
        # Jeśli plik nie istnieje, zwróć prosty tekst, żeby appka działała
        print(f"OSTRZEŻENIE: Nie znaleziono szablonu index.html: {e}")
        return "<h1>Word Syllable Game Backend</h1><p>Template 'index.html' not found.</p>"

# --- Endpoint API: Pobranie dzisiejszej zagadki ---

@app.route('/api/puzzle/today', methods=['GET'])
def get_today_puzzle():
    """Zwraca dane potrzebne do rozpoczęcia dzisiejszej gry."""
    today_date = date.today()
    print(f"Żądanie API dla zagadki dnia: {today_date}")

    word_ids_str = database.get_daily_puzzle(today_date)
    word_ids = []

    if word_ids_str:
        # Zagadka na dziś już istnieje, użyj jej ID
        print("Znaleziono istniejącą zagadkę.")
        word_ids = [int(id_str) for id_str in word_ids_str.split(',') if id_str.isdigit()]
    else:
        # Brak zagadki na dziś, wylosuj nowe słowa
        print("Brak istniejącej zagadki, losowanie nowych słów...")
        # TODO: Można dodać konfigurację liczby słów i dni wykluczenia
        words_for_puzzle = database.get_words_for_puzzle(count=5, exclude_used_within_days=30)

        if len(words_for_puzzle) < 5:
            # Nie udało się znaleźć wystarczającej liczby unikalnych słów
            print(f"BŁĄD KRYTYCZNY: Nie znaleziono wystarczającej liczby ({len(words_for_puzzle)}/5) słów w bazie danych.")
            # W MVP zwracamy błąd. W przyszłości można obsłużyć to inaczej.
            return jsonify({"error": "Not enough unique words available in the database."}), 500

        word_ids = [word['id'] for word in words_for_puzzle]

        # Zapisz nową zagadkę dnia
        print(f"Zapisywanie nowej zagadki z ID: {word_ids}")
        database.save_daily_puzzle(today_date, word_ids)

        # Zaktualizuj datę ostatniego użycia dla wylosowanych słów
        print("Aktualizacja daty ostatniego użycia słów...")
        database.update_last_used_date(word_ids, today_date)

    # Mamy już listę word_ids (zapisanych lub nowo wylosowanych)
    # Pobierz szczegóły tych słów
    print(f"Pobieranie szczegółów dla słów o ID: {word_ids}")
    word_details = database.get_word_details(word_ids)

    if not word_details or len(word_details) != len(word_ids):
         print(f"BŁĄD: Nie udało się pobrać szczegółów dla wszystkich wymaganych ID słów ({len(word_details)}/{len(word_ids)}).")
         return jsonify({"error": "Failed to retrieve word details for the puzzle."}), 500

    # Przygotuj dane do wysłania do frontendu
    hints = []
    all_syllables = []
    correct_words_info = {} # Słownik: { word_id: ["syl1", "syl2", ...] }

    for word_row in word_details:
        word_id = word_row['id']
        hint_text = word_row['hint']
        syllables_str = word_row['syllables'] # np. "za-gad-ka"

        # Dodaj podpowiedź
        hints.append({"id": word_id, "hint": hint_text})

        # Podziel string sylab na listę i dodaj do ogólnej puli
        current_syllables = syllables_str.split('-')
        all_syllables.extend(current_syllables)

        # Zapisz poprawną kolejność sylab dla tego słowa
        correct_words_info[str(word_id)] = current_syllables # Użyj string jako klucza w JSON

    # Potasuj wszystkie zebrane sylaby
    random.shuffle(all_syllables)

    # Przygotuj finalną odpowiedź JSON
    response_data = {
        "puzzleDate": today_date.strftime('%Y-%m-%d'),
        "hints": hints,
        "syllables": all_syllables,
        "correctWordsInfo": correct_words_info # Frontend użyje tego do weryfikacji
    }

    print(f"Zwracanie danych zagadki: {len(hints)} podpowiedzi, {len(all_syllables)} sylab.")
    return jsonify(response_data)

@app.route('/api/puzzle/check', methods=['POST'])
def check_word_attempt():
    """Sprawdza, czy podane sylaby pasują do słowa o danym ID."""
    data = request.get_json()
    print(f"Otrzymano próbę sprawdzenia słowa: {data}")

    # Sprawdzenie, czy otrzymano potrzebne dane
    if not data or 'wordId' not in data or 'attemptedSyllables' not in data:
        return jsonify({"correct": False, "message": "Missing data. Required: 'wordId', 'attemptedSyllables'."}), 400

    word_id = data.get('wordId')
    attempted_syllables = data.get('attemptedSyllables')

    # Prosta walidacja danych
    if not isinstance(word_id, int):
         return jsonify({"correct": False, "message": "Invalid wordId."}), 400
    if not isinstance(attempted_syllables, list): # Oczekujemy listy sylab
        return jsonify({"correct": False, "message": "Invalid attemptedSyllables format (should be a list)."}), 400

    try:
        # Pobierz poprawne dane słowa z bazy
        word_details_list = database.get_word_details([word_id])

        if not word_details_list:
            print(f"Błąd: Nie znaleziono słowa o ID: {word_id}")
            return jsonify({"correct": False, "message": f"Word with ID {word_id} not found."}), 404 # 404 Not Found

        word_detail = word_details_list[0] # Powinien być tylko jeden wynik
        correct_syllables_str = word_detail['syllables'] # np. "za-gad-ka"
        correct_syllables_list = correct_syllables_str.split('-')

        # Porównaj listę prób z poprawną listą sylab
        is_correct = (attempted_syllables == correct_syllables_list)

        print(f"Sprawdzenie dla ID {word_id}: Próba {attempted_syllables}, Poprawne {correct_syllables_list} -> Wynik: {is_correct}")

        return jsonify({"correct": is_correct})

    except Exception as e:
        # Ogólny błąd serwera
        print(f"Krytyczny błąd podczas sprawdzania słowa: {e}")
        return jsonify({"correct": False, "message": "An internal server error occurred during word check."}), 500

# --- Endpoint API: Zapisywanie wyniku gracza ---
@app.route('/api/scores', methods=['POST'])
def submit_score():
    """Zapisuje wynik gracza dla dzisiejszej zagadki."""
    data = request.get_json()
    print(f"Otrzymano próbę zapisu wyniku: {data}")

    # Sprawdzenie, czy otrzymano potrzebne dane
    if not data or 'nickname' not in data or 'timeSeconds' not in data:
        return jsonify({"success": False, "message": "Missing data. Required: 'nickname', 'timeSeconds'."}), 400

    nickname = data.get('nickname')
    time_seconds = data.get('timeSeconds')

    # Prosta walidacja danych
    if not isinstance(nickname, str) or not nickname.strip():
        return jsonify({"success": False, "message": "Invalid nickname."}), 400
    if not isinstance(time_seconds, int) or time_seconds < 0:
         return jsonify({"success": False, "message": "Invalid timeSeconds."}), 400

    # Pobierz dzisiejszą datę
    today_date = date.today()

    # Zapisz wynik w bazie danych
    try:
        score_id = database.save_score(today_date, nickname.strip(), time_seconds)
        if score_id:
            print(f"Zapisano wynik ID: {score_id}")
            return jsonify({"success": True, "message": "Score submitted successfully."}), 201 # 201 Created
        else:
            # Jeśli save_score zwróciło None z powodu błędu bazy (obsłużonego w database.py)
             print("Błąd: database.save_score zwróciło None.")
             return jsonify({"success": False, "message": "Failed to save score due to a database error."}), 500
    except Exception as e:
        # Ogólny błąd serwera
        print(f"Krytyczny błąd podczas zapisywania wyniku: {e}")
        return jsonify({"success": False, "message": "An internal server error occurred."}), 500

# --- Endpoint API: Pobieranie rankingu na dziś ---
@app.route('/api/scores/today', methods=['GET'])
def get_leaderboard():
    """Pobiera dzienny ranking (top 10) dla dzisiejszej zagadki."""
    print("Otrzymano żądanie rankingu na dziś.")
    today_date = date.today()

    try:
        # Pobierz wyniki z bazy (domyślnie top 10 wg database.py)
        scores_data = database.get_daily_scores(today_date) # Limit jest w database.py

        # Przekształć obiekty sqlite3.Row na listę słowników
        leaderboard = [
            {"nickname": row['nickname'], "timeSeconds": row['time_seconds']}
            for row in scores_data
        ]

        print(f"Zwracanie {len(leaderboard)} wyników rankingu.")
        return jsonify(leaderboard)

    except Exception as e:
        # Ogólny błąd serwera
        print(f"Krytyczny błąd podczas pobierania rankingu: {e}")
        return jsonify({"error": "An internal server error occurred while fetching the leaderboard."}), 500


# --- Uruchomienie aplikacji ---
if __name__ == '__main__':
    print("Uruchamianie serwera Flask...")
    # Sprawdzenie i inicjalizacja bazy przed uruchomieniem serwera (opcjonalne, ale dobre)
    try:
        print("Sprawdzanie połączenia z bazą danych przed startem...")
        conn = database.get_db_connection()
        conn.close()
        print("Połączenie z bazą danych OK.")
        # Można tu dodać wywołanie populate_words_from_file, jeśli potrzebne
        # database.populate_words_from_file()
    except Exception as e:
        print(f"KRYTYCZNY BŁĄD: Nie można połączyć się lub zainicjalizować bazy danych: {e}")
        # Można zdecydować o zakończeniu działania aplikacji, jeśli baza jest niezbędna
        # import sys
        # sys.exit(1)

    app.run(debug=True, host='0.0.0.0', port=5000)