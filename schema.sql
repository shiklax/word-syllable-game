-- Plik: schema.sql

-- Tabela przechowująca słowa, ich podpowiedzi, podział na sylaby i datę ostatniego użycia
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unikalny identyfikator słowa
    word TEXT NOT NULL UNIQUE,           -- Słowo (unikalne)
    hint TEXT NOT NULL,                  -- Podpowiedź do słowa
    syllables TEXT NOT NULL,             -- Sylaby słowa oddzielone myślnikiem (np. "za-gad-ka")
    last_used_date DATE                  -- Data (YYYY-MM-DD), kiedy słowo było ostatnio częścią zagadki
);

-- Tabela przechowująca ID słów wybrane do zagadki na konkretny dzień
CREATE TABLE IF NOT EXISTS daily_puzzles (
    puzzle_date DATE PRIMARY KEY,       -- Data zagadki (YYYY-MM-DD), unikalna
    word_ids TEXT NOT NULL              -- ID słów z tabeli 'words' oddzielone przecinkami (np. "1,5,23,42,100")
);

-- Tabela przechowująca wyniki graczy dla poszczególnych dni
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unikalny identyfikator wyniku
    puzzle_date DATE NOT NULL,           -- Data zagadki, do której odnosi się wynik
    nickname TEXT NOT NULL,              -- Nick gracza
    time_seconds INTEGER NOT NULL,       -- Czas ukończenia zagadki w sekundach
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Kiedy wynik został zapisany
);

-- Opcjonalnie: Można dodać indeksy dla szybszego wyszukiwania, jeśli baza by się rozrosła
-- CREATE INDEX IF NOT EXISTS idx_word_last_used ON words (last_used_date);
-- CREATE INDEX IF NOT EXISTS idx_scores_date_time ON scores (puzzle_date, time_seconds);