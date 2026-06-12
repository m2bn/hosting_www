# Backup And Restore Runbook

## Cel

Ten runbook opisuje bazową procedurę backupu i testowego restore platformy SaaS. Backup obejmuje PostgreSQL, metadane MinIO/S3, pliki deploymentów, konfigurację platformy oraz bezpieczne fingerprinty sekretów i kluczy. Artefakt backupu jest zawsze szyfrowany przed zapisem.

## Zakres Backupów

- PostgreSQL: preferowany `pg_dump --no-owner --no-privileges` przy `DATABASE_URL`; fallback developerski używa `django dumpdata`.
- MinIO/S3 metadata: lista kluczy, rozmiary, ETag i czas modyfikacji bez pobierania wartości sekretów.
- Pliki deploymentów: lokalny katalog `STATIC_DEPLOYMENT_LOCAL_ROOT`; dla S3 źródłem prawdy pozostaje bucket i metadane obiektów.
- Konfiguracja platformy: allowlista kluczy `BACKUP_PLATFORM_CONFIG_KEYS`.
- Sekrety i klucze: tylko fingerprinty z `BACKUP_SECRET_FINGERPRINT_KEYS`, nigdy plaintext.
- Retencja: `BACKUP_RETENTION_DAYS`, domyślnie 30 dni.

## Wymagane Zmienne

- `BACKUP_ENCRYPTION_KEY`: klucz Fernet lub wysokiej entropii passphrase. Musi być przechowywany poza backupowanym artefaktem.
- `BACKUP_OUTPUT_DIR`: katalog docelowy backupów.
- `BACKUP_RETENTION_DAYS`: liczba dni retencji.
- `DATABASE_URL`: wymagany do produkcyjnego `pg_dump`.
- `APP_ENV`: `production`, `staging` albo `development`.

## Uruchomienie Backupu

```bash
python scripts/backup.py
```

Wynik zawiera `backup_id`, ścieżkę do pliku `*.tar.gz.enc` i SHA-256 zaszyfrowanego artefaktu. Logi nie zawierają sekretów, tokenów, kluczy Stripe ani wartości zmiennych środowiskowych oznaczonych jako sekretne.

## Weryfikacja Backupu

```bash
python manage.py test_restore_backup /path/to/backup.tar.gz.enc
```

Weryfikacja sprawdza:

- możliwość odszyfrowania artefaktu,
- obecność manifestu,
- obecność komponentów: `postgresql`, `s3_metadata`, `deployment_files`, `platform_config`, `secret_fingerprints`.

## Restore Do Staging

Restore bazowy rozpakowuje backup do katalogu staging i wykonuje walidację manifestu. Nie nadpisuje production i odmawia pracy przy `APP_ENV=production`.

```bash
APP_ENV=staging python scripts/restore_staging.py /path/to/backup.tar.gz.enc --restore-dir /restore/staging
```

Dla środowiska innego niż `staging` wymagane jest jawne potwierdzenie:

```bash
python manage.py test_restore_backup /path/to/backup.tar.gz.enc --execute --restore-dir /restore/staging --confirm-staging
```

## Procedura Awaryjnego Odtworzenia Środowiska

1. Utwórz nowe środowisko staging albo recovery bez dostępu publicznego.
2. Pobierz ostatni poprawny backup oraz odpowiadający plik SHA-256.
3. Zweryfikuj sumę kontrolną zaszyfrowanego artefaktu.
4. Uruchom `test_restore_backup` bez `--execute`.
5. Rozpakuj backup do staging przez `restore_staging.py`.
6. Odtwórz PostgreSQL z `payload/postgresql/dump.sql`.
7. Porównaj metadane MinIO/S3 z `payload/s3/objects.json`.
8. Odtwórz pliki deploymentów z `payload/deployment_files` albo zsynchronizuj bucket S3 zgodnie z manifestem.
9. Porównaj fingerprinty sekretów z aktywnym secrets managerem.
10. Uruchom testy smoke: logowanie, lista organizacji, odczyt projektu, odczyt deploymentu, odczyt domeny.
11. Dopiero po akceptacji incident commandera przełącz ruch lub wykonaj restore produkcji manualną procedurą infrastrukturalną.

## RPO/RTO

- MVP RPO: 24 godziny dla pełnego backupu dziennego.
- MVP RTO: 4 godziny dla odtworzenia staging/recovery.
- Docelowo: RPO 1 godzina dla bazy i metadanych, RTO 1 godzina dla krytycznych tenantów.

## Bezpieczeństwo

- Backupy muszą być szyfrowane przed zapisem na dysk lub do object storage.
- Dostęp do `BACKUP_OUTPUT_DIR` i bucketu backupowego ma osobny service account zgodny z least privilege.
- Klucz `BACKUP_ENCRYPTION_KEY` nie może znajdować się w backupie ani w repozytorium.
- Restore nie może nadpisywać production bez ręcznej procedury awaryjnej i jawnej akceptacji.
- Logi backup/restore nie mogą zawierać sekretów, tokenów, haseł ani pełnych payloadów webhooków.

## Test Restore

Test restore należy wykonywać co najmniej raz na sprint oraz po zmianach w modelach danych, storage lub konfiguracji sekretów. Wynik testu powinien być zapisany w systemie audytu operacyjnego jako: data, `backup_id`, osoba wykonująca, wynik, RPO/RTO zaobserwowane podczas testu.
