# Infrastructure Runbook

## Cel

Ten runbook opisuje bazową obsługę infrastruktury jako kod dla platformy SaaS hostingu stron i aplikacji klientów. Aktualny katalog `infra/terraform` jest provider-agnostic scaffoldem: definiuje moduły, środowiska, zmienne, wymagania bezpieczeństwa i przykładowe konfiguracje bez wyboru konkretnej chmury.

## Zakres

Infrastruktura obejmuje:

- PostgreSQL dla control plane.
- Redis dla cache, rate limiting i krótkotrwałych stanów.
- RabbitMQ dla Celery i kolejek workerów.
- S3-compatible storage dla deploymentów, backupów i artefaktów.
- Kubernetes cluster dla runtime aplikacji klientów.
- Prywatny container registry.
- DNS records dla dashboardu, API i wildcard runtime.
- Integrację z secrets managerem.
- Monitoring stack: Prometheus, Grafana, Loki i tracing.

## Struktura

- `infra/terraform/envs/staging` - wejście Terraform dla staging.
- `infra/terraform/envs/production` - wejście Terraform dla production.
- `infra/terraform/stacks/platform` - wspólny stack platformy.
- `infra/terraform/modules/*` - moduły zasobów, obecnie jako kontrakty provider-agnostic.

## Zasady Bezpieczeństwa

- Nie commitujemy sekretów, haseł, tokenów, kubeconfigów, private keys ani prawdziwych backend credentials.
- Terraform state musi być w zdalnym, szyfrowanym backendzie z blokadą stanu.
- Dostęp do state jest traktowany jak dostęp do sekretów.
- Production `apply` wymaga review planu i zatwierdzenia przez operatora.
- Zmiany production uruchamiamy z CI na chronionej gałęzi.
- Zasoby produkcyjne muszą mieć szyfrowanie w spoczynku i transmisji, prywatne endpointy tam gdzie możliwe, audit logs i deletion protection.

## Pierwsze Uruchomienie Staging

1. Wybierz provider chmurowy albo lokalny provider testowy.
2. Podmień placeholdery `terraform_data` w modułach na konkretne zasoby providera.
3. Skonfiguruj remote backend:

```bash
cd infra/terraform/envs/staging
cp backend.tf.example backend.tf
```

4. Uzupełnij backend bez commitowania sekretów.
5. Przygotuj zmienne:

```bash
cp terraform.tfvars.example terraform.tfvars
```

6. Uzupełnij tylko wartości niebędące sekretami.
7. Uruchom:

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

## Pierwsze Uruchomienie Production

1. Upewnij się, że staging przeszedł `plan`, `apply`, testy dymne i test restore.
2. Skonfiguruj oddzielny backend state dla production.
3. Użyj oddzielnych kont lub projektów cloud dla production.
4. Przygotuj plan:

```bash
cd infra/terraform/envs/production
terraform init
terraform validate
terraform plan -var-file=terraform.tfvars -out=production.tfplan
```

5. Przekaż plan do review.
6. Po zatwierdzeniu uruchom:

```bash
terraform apply production.tfplan
```

7. Usuń lokalny plan, jeśli zawiera dane wrażliwe.

## Separacja Środowisk

- Staging i production mają osobne katalogi, zmienne, state i DNS.
- Production nie może współdzielić bucketów, baz danych, registry ani secrets manager paths ze staging.
- Konta serwisowe CI muszą mieć uprawnienia ograniczone do jednego środowiska.

## Sekrety

Sekrety przekazujemy wyłącznie przez:

- zewnętrzny secrets manager,
- GitHub Actions secrets,
- zmienne środowiskowe CI,
- ręczne, lokalne wartości poza repozytorium podczas prac operatorskich.

Nie zapisujemy sekretów w:

- `terraform.tfvars.example`,
- `backend.tf.example`,
- outputach Terraform,
- logach CI,
- dokumentacji.

## DNS

DNS records w przykładach obejmują:

- `app` dla dashboardu/control plane,
- wildcard `*.apps` dla runtime aplikacji klientów.

Przed zmianą production DNS:

- ustaw krótszy TTL co najmniej jeden cykl deployu wcześniej,
- zweryfikuj cert-manager i ACME challenge,
- przygotuj rollback wartości rekordu.

## Monitoring

Monitoring stack musi obejmować:

- metryki Kubernetes i control plane,
- logi aplikacyjne,
- audit logs,
- alerty dla baz danych, kolejek, webhooków Stripe, certyfikatów i deploymentów,
- dashboardy operatora.

Alert routing nie może ujawniać sekretów ani danych klientów.

## Backup I Restore

Infrastruktura musi wspierać procedury z `docs/runbooks/backup-and-restore.md`:

- backup PostgreSQL,
- backup metadanych storage,
- backup artefaktów deploymentów,
- backup konfiguracji platformy,
- szyfrowanie backupów,
- okresowy test restore na staging.

## Rollback Zmian Infrastruktury

1. Zatrzymaj dalsze deploye aplikacyjne, jeśli zmiana dotyczy runtime.
2. Zidentyfikuj ostatni poprawny plan i commit IaC.
3. Wykonaj `terraform plan` dla rollbacku.
4. Zweryfikuj wpływ na dane stanowe.
5. Dla production wymagaj zatwierdzenia operatora.
6. Po rollbacku sprawdź healthchecki, kolejki, deploymenty i alerty.

## Checklist Przed Production Apply

- Plan był wygenerowany z aktualnej gałęzi.
- Plan został przejrzany przez drugą osobę.
- Brak sekretów w diffie i planie.
- Remote state jest szyfrowany i zablokowany.
- Backup i restore są aktualne.
- Maintenance window jest ustalone, jeśli zmiana może powodować przerwę.
- Rollback jest opisany i możliwy.
- Alerty są aktywne.

## Następne Kroki Po Wyborze Chmury

- Zastąpić `terraform_data` realnymi zasobami providera.
- Dodać moduł sieciowy VPC/VNet.
- Dodać IAM least privilege dla operatorów, CI i workloadów.
- Dodać polityki state backendu.
- Dodać testy IaC: `terraform validate`, `tflint`, `tfsec` albo `checkov`.
- Podłączyć plan/apply do GitHub Actions z manual approval dla production.
