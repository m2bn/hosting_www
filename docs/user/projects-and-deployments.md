# Projekty i deploymenty

## Czym jest projekt

Projekt reprezentuje jedną stronę albo aplikację. Należy do organizacji i ma własne deploymenty, domeny, sekrety, logi oraz limity zużycia.

## Utworzenie projektu

1. Otwórz organizację.
2. Przejdź do listy projektów.
3. Wybierz utworzenie projektu.
4. Podaj nazwę projektu.
5. Zatwierdź formularz.

Jeśli organizacja osiągnęła limit projektów w planie, utworzenie kolejnego projektu może zostać zablokowane.

## Deployment statycznej strony

Deployment statycznej strony służy do publikacji plików HTML, CSS, JavaScript, obrazów i innych statycznych zasobów.

1. Otwórz projekt.
2. Przejdź do sekcji deploymentów.
3. Wybierz deployment statycznej strony.
4. Przygotuj plik ZIP z zawartością strony.
5. Wyślij plik ZIP.
6. Poczekaj na walidację, skanowanie i publikację.

Platforma sprawdza plik ZIP przed wdrożeniem. Deployment może zostać odrzucony, jeśli plik jest za duży, zawiera niedozwolone ścieżki, symlinki, zbyt wiele plików albo wykryte zagrożenie.

## Deployment aplikacji kontenerowej

Deployment kontenerowy służy do uruchomienia aplikacji budowanej z `Dockerfile`.

1. Otwórz projekt.
2. Przejdź do sekcji deploymentów.
3. Wybierz deployment aplikacji kontenerowej.
4. Przygotuj ZIP z kodem aplikacji i plikiem `Dockerfile`.
5. Dodaj `.dockerignore`, aby pominąć niepotrzebne pliki.
6. Wyślij ZIP.
7. Poczekaj na build, skanowanie obrazu i deployment.

Deployment zostanie zablokowany, jeśli obraz zawiera krytyczne podatności albo aplikacja przekracza limity planu.

## Skanowanie artefaktów

Platforma skanuje przesłane artefakty, zależności i obrazy kontenerowe. Wyniki skanowania są dostępne w panelu projektu. Użytkownicy widzą tylko wyniki należące do ich organizacji i projektu.

Jeśli deployment zostanie zablokowany przez skan bezpieczeństwa, zobaczysz bezpieczny komunikat z informacją, że deployment nie może zostać wykonany. Szczegóły techniczne są ograniczone, aby nie ujawniać wrażliwych danych.

## Usunięcie projektu

Usunięcie projektu zwykle zaczyna się od soft delete. Oznacza to, że projekt przestaje być aktywny, ale dane mogą być przechowywane przez określony czas zgodnie z polityką retencji.

1. Otwórz ustawienia projektu.
2. Wybierz usunięcie projektu.
3. Potwierdź decyzję.

Usunięcie projektu nie powinno być używane jako szybka metoda usuwania incydentu bezpieczeństwa. W takich przypadkach skontaktuj się z administratorem lub supportem.
