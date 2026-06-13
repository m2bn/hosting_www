# Logi i rollback

## Podgląd logów

Logi pomagają sprawdzić, co wydarzyło się podczas builda, deploymentu albo działania aplikacji.

1. Otwórz projekt.
2. Przejdź do sekcji deploymentów.
3. Wybierz konkretny deployment.
4. Otwórz logi builda albo deploymentu.

Nie zapisuj w logach haseł, tokenów, kluczy API ani sekretów. Jeśli sekret przypadkowo trafi do logów, potraktuj go jako ujawniony i wykonaj rotację.

## Statusy deploymentu

- `queued`: deployment czeka w kolejce.
- `building`: trwa build.
- `scanning`: trwa skanowanie bezpieczeństwa.
- `deploying`: trwa publikacja.
- `active`: deployment jest aktywny.
- `failed`: deployment nie powiódł się.
- `rolled_back`: deployment został zastąpiony przez rollback.

## Rollback

Rollback przywraca poprzedni działający deployment.

1. Otwórz projekt.
2. Przejdź do deploymentów.
3. Wybierz wcześniejszy deployment, który chcesz przywrócić.
4. Wybierz rollback.
5. Potwierdź decyzję.

Rollback nie usuwa nowszego deploymentu. Zmienia aktywną wersję aplikacji na wybraną wcześniejszą wersję.

## Kiedy używać rollbacku

Rollback jest przydatny, gdy:

- nowa wersja aplikacji ma błąd,
- deployment zakończył się sukcesem technicznym, ale aplikacja działa niepoprawnie,
- konfiguracja domeny albo routingu wskazuje na problem po wdrożeniu,
- chcesz szybko wrócić do ostatniej stabilnej wersji.
