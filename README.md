# Automatyzacja Worklogów Jira

Skrypt Python do automatycznego przesyłania worklogów z plików Excel do Jira Server v8.13.8.

## Funkcje

- ✅ Automatyczne czytanie plików Excel z katalogu `INPUT_DIR`
- ✅ Wykrywanie kluczy zadań Jira w formacie `[ABC-123]`
- ✅ Konwersja formatów czasu z Excel do formatu Jira (np. "01:30:00" → "1h 30m")
- ✅ Synchronizacja worklogów z automatycznym śledzeniem już zsynchronizowanych zadań
- ✅ Automatyczne oznaczanie zsynchronizowanych worklogów w logach JSON
- ✅ Przenoszenie przetworzonych plików do katalogu `OUTPUT_DIR`
- ✅ Obsługa domyślnej daty (dzisiejsza) lub niestandardowej
- ✅ Szczegółowe logowanie do pliku i konsoli

## Wymagania

```bash
pip install pandas openpyxl
```

## Konfiguracja

### ⚙️ **Krok 1: Ustaw URL serwera Jira**

**W pliku `worklog_copilot.py` linia 9 pozwala skonfigurować URL serwera Jira:**
```python
JIRA_BASE_URL = "https://jira.twoja-firma.com"
```

### 🔐 **Krok 2: Wybierz metodę logowania**

### Metoda 1: Interaktywny skrypt BAT (ZALECANA)

Użyj skryptu `run_worklog.bat`, który zapyta o dane dostępowe:

```bash
# Windows - skrypt zapyta o login:hasło
run_worklog.bat

# Z konkretną datą
run_worklog.bat 20250918
```

### Metoda 2: Bezpośrednie wywołanie Python

```bash
# Z argumentami w linii poleceń (format: login:hasło)
python worklog_copilot.py --jira-credentials "username:password"

# Z konkretną datą
python worklog_copilot.py 20250918 --jira-credentials "username:password"
```

### ⚠️ Bezpieczeństwo

- **Zalecane:** Użyj API token zamiast hasła
- Przejdź do ustawień profilu w Jira → Wygeneruj API token
- Nigdy nie commituj haseł do repozytorium kodu!

### 📝 Dlaczego nie ma pliku konfiguracyjnego ani zmiennych środowiskowych?

Ze względów bezpieczeństwa nie używamy zewnętrznych plików ani zmiennych środowiskowych:
- ✅ **Bezpieczne:** Dane logowania są przekazywane bezpośrednio do procesu Python
- ✅ **Izolowane:** Hasła nie są dostępne dla innych procesów w systemie  
- ✅ **Automatycznie czyszczone:** Dane znikają po zakończeniu procesu
- ✅ **Brak ryzyka:** Nie ma plików z hasłami ani zmiennych w systemie

**Problemy z alternatywami:**
- ❌ **Pliki konfiguracyjne:** Ryzyko pozostawienia haseł na dysku
- ❌ **Zmienne środowiskowe:** Dostępne dla wszystkich procesów, mogą pozostać w pamięci
- ❌ **Historię poleceń:** W niektórych shellach argumenty mogą być zapisywane

**Nasze rozwiązanie:** Dane logowania są przekazywane przez argumenty wiersza poleceń bezpośrednio do procesu Python i automatycznie znikają po zakończeniu.

## Struktura katalogów

```
├── worklog_copilot.py    # Główny skrypt Python
├── run_worklog.bat       # Interaktywny skrypt Windows (ZALECANY)
├── README.md             # Ta dokumentacja
├── in/                   # Katalog z plikami Excel do przetworzenia
│   ├── 20250918.xlsx
│   ├── 20250917.xlsx
│   └── ...
├── out/                  # Katalog z przetworzonymi plikami
└── sync_logs/            # Logi synchronizacji (pliki JSON)
    ├── 20250918_sync.json
    └── ...
```

## Format pliku Excel

Plik Excel musi zawierać kolumny:

| TASK | COMMENT | TIME |
|------|---------|------|
| `[ABC-123] Nazwa zadania` | Komentarz do worklog | 01:30:00 |

- **TASK**: Link lub opis zawierający klucz zadania w nawiasach `[ABC-123]`
- **COMMENT**: Komentarz do worklog
- **TIME**: Czas w formacie HH:MM:SS (np. "01:30:00" dla 1 godziny 30 minut)

## Użycie

### 🚀 **Metoda najprostsza - Windows BAT**

```bash
# Interaktywne logowanie (skrypt zapyta o login:hasło)
run_worklog.bat

# Synchronizacja konkretnej daty
run_worklog.bat 20250918
```

### 🐍 **Bezpośrednie wywołanie Python**

```bash
# Synchronizacja z dzisiejszą datą
python worklog_copilot.py --jira-credentials "username:password"

# Synchronizacja z konkretną datą
python worklog_copilot.py 20250918 --jira-credentials "username:password"

# Pomoc
python worklog_copilot.py --help
```

**⚠️ Uwaga o bezpieczeństwie argumentów:**
- Argumenty mogą być widoczne w historii poleceń - używaj skryptu BAT
- W środowisku produkcyjnym zawsze używaj interaktywnego `run_worklog.bat`

## Proces działania

1. **Odczyt pliku:** Skrypt szuka pliku `YYYYMMDD.xlsx` w katalogu `in`
2. **Parsowanie:** Wyciąga worklogi z kolumn TASK, COMMENT, TIME
3. **Filtrowanie:** Sprawdza pliki JSON w `sync_logs/` aby pominąć już zsynchronizowane zadania
4. **Walidacja:** Sprawdza format czasu i klucz zadania Jira
5. **Ustawienie daty/czasu:** Worklog otrzymuje datę z parametru (lub dzisiejszą) i godzinę 15:00
6. **Synchronizacja:** Dodaje worklogi do Jira przez REST API
7. **Aktualizacja:** Zapisuje informacje o zsynchronizowanych zadaniach do plików JSON w `sync_logs/`
8. **Przenoszenie:** Przesuwa przetworzony plik do katalogu `out` **tylko jeśli wszystkie worklogi zostały pomyślnie zsynchronizowane**

### ⏰ **Ważne o dacie i czasie worklogów:**
- **Data:** Używana jest data z parametru (np. `20250918`) lub dzisiejsza jeśli nie podano
- **Czas:** Zawsze ustawiony na **15:00** (3:00 PM)
- **Format dla Jira:** `2025-09-18T15:00:00.000+0000`
- **Dlaczego 15:00?** Standardowy czas "wykonania" zadań w środku dnia roboczego

## Logowanie

Wszystkie operacje są logowane do konsoli z informacjami o postępie i błędach.

Dodatkowo skrypt tworzy pliki JSON w katalogu `sync_logs/` które śledzą zsynchronizowane zadania.

## Bezpieczeństwo

- **Zawsze sprawdzaj dane przed synchronizacją**
- Używaj API token zamiast hasła
- Trzymaj dane autoryzacyjne w bezpiecznym miejscu
- Sprawdzaj logi pod kątem błędów

## Rozwiązywanie problemów

### Błąd autoryzacji Jira
```
Missing Jira credentials. Use --jira-credentials login:password
```
- Sprawdź URL, nazwę użytkownika i hasło/token
- Upewnij się, że konto ma uprawnienia do dodawania worklogów

### Nieprawidłowy format czasu
```
Invalid time format '00:00:00' for task ABC-123
```
- Sprawdź czy czas w Excel jest większy niż 00:00:00
- Upewnij się, że komórka TIME zawiera poprawny format czasowy

### Brak pliku
```
File does not exist: in\20250919.xlsx
```
- Sprawdź czy plik istnieje w katalogu `in`
- Upewnij się, że nazwa pliku to `YYYYMMDD.xlsx`

### Błąd synchronizacji
```
Authentication error for ABC-123: 401 Unauthorized - check credentials
Failed to add worklog to ABC-123 - will retry on next run
File kept in in/ - 1 worklogs failed to synchronize
```
- Plik pozostaje w katalogu `in/` dla ponownej próby
- Sprawdź dane logowania
- Uruchom ponownie skrypt po naprawieniu problemu

## Przykład działania

### Interaktywne logowanie:
```cmd
PS> run_worklog.bat 20250918
================================
   WORKLOG JIRA SYNCHRONIZER
================================

Podaj dane logowania do Jira:
Login:haslo (np. jan.kowalski:password123): jan.kowalski:password123

Dane logowania: jan.kowalski:password123

Synchronizacja worklogów dla daty 20250918...
Connecting to: https://jira.twoja-firma.com as jan.kowalski
Processing file: in\20250918.xlsx
Found 6 worklogs
Found 6 unsynchronized worklogs
Adding worklog to ABC-123: 15m (date: 2025-09-18)
Successfully added worklog to ABC-123 (ID: 1637905)
Adding worklog to ABC-124: 30m (date: 2025-09-18)
Successfully added worklog to ABC-124 (ID: 1637906)
Saved 6 synchronized worklogs to log
Processing completed. Synchronized 6/6 worklogs
Moved to: out\20250918.xlsx
```

**Zwróć uwagę:** Worklogi będą dodane z datą `2025-09-18` i godzinę `15:00:00` w strefie czasowej `+0200` (Europe/Warsaw).

## Autor

Skrypt został stworzony dla automatyzacji worklogów w Jira Server v8.13.8.