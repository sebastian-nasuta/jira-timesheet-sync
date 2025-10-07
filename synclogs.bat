@echo off
REM Skrypt wsadowy do uruchamiania worklog_copilot.py z interaktywnym logowaniem
REM 
REM Użycie: 
REM   synclogs.bat                 - synchronizacja dzisiejszego dnia
REM   synclogs.bat 20250918        - synchronizacja konkretnej daty

setlocal EnableDelayedExpansion

REM Zabezpieczenie - wyczyść zmienne na wypadek przerwania
set JIRA_CREDENTIALS=
set USERNAME=

echo ================================
echo    WORKLOG JIRA SYNCHRONIZER
echo ================================
echo.

REM Pobierz dane logowania do Jira
echo Enter your Jira login credentials:
set /p JIRA_CREDENTIALS="Login:password (np. jan.kowalski:password123): "

REM Sprawdź czy podano dane logowania
if "%JIRA_CREDENTIALS%"=="" (
    echo.
    echo ERROR: No login credentials provided!
    echo Press any key to close...
    pause >nul
    exit /b 1
)

REM Sprawdź czy dane logowania mają format login:hasło
echo "%JIRA_CREDENTIALS%" | findstr ":" >nul
if errorlevel 1 (
    echo.
    echo ERROR: Login credentials must be in the format login:password!
    REM Wyczyść dane przed wyjściem
    set JIRA_CREDENTIALS=
    echo Press any key to close...
    pause >nul
    exit /b 1
)

REM Pokaż tylko nazwę użytkownika (bez hasła)
for /f "tokens=1 delims=:" %%a in ("%JIRA_CREDENTIALS%") do set USERNAME=%%a
echo.
echo User: %USERNAME%
echo.

REM Sprawdź argumenty i uruchom odpowiedni tryb
if "%1"=="" (
    echo Synchronizing worklogs for today...
    echo.
    python worklog_copilot.py --jira-credentials "%JIRA_CREDENTIALS%"
) else (
    echo Synchronizing worklogs for date %1...
    echo.
    python worklog_copilot.py %1 --jira-credentials "%JIRA_CREDENTIALS%"
)

REM Sprawdź wynik wykonania skryptu Python
if errorlevel 1 (
    echo.
    echo ERROR: Script failed!
) else (
    echo.
    echo Synchronization completed successfully.
)

:cleanup
REM Wyczyść zmienne z hasłem ze względów bezpieczeństwa
set JIRA_CREDENTIALS=
set USERNAME=

echo.
echo Press any key to close...
pause >nul