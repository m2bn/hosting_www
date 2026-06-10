# Model domenowy backendu Django

## 1. Cel i założenia

Ten dokument opisuje model domenowy control plane platformy SaaS do hostingu stron i aplikacji klientów. Nie jest jeszcze implementacją modeli Django, ale stanowi kontrakt projektowy dla przyszłych aplikacji backendowych, migracji, API, autoryzacji i testów.

Założenia bazowe:

- system jest multi-tenant;
- podstawową jednostką tenantową jest `Organization`;
- większość zasobów biznesowych należy do organizacji, a zasoby runtime dodatkowo do projektu i środowiska;
- każda operacja biznesowa musi mieć jawny tenant context;
- autoryzacja jest egzekwowana po stronie serwera;
- dane audytowe i bezpieczeństwa są append-only z perspektywy aplikacji;
- pola wrażliwe są minimalizowane, maskowane, hashowane albo szyfrowane zgodnie z security baseline.

## 2. Opis encji

### User

Reprezentuje konto osoby korzystającej z platformy albo operatora platformy.

Kluczowe pola:

- `id`: UUID.
- `email`: unikalny adres e-mail, case-insensitive.
- `password_hash`: hash hasła zarządzany przez Django.
- `full_name`: nazwa wyświetlana.
- `is_active`: czy konto może się logować.
- `is_email_verified`: czy adres e-mail został potwierdzony.
- `is_platform_staff`: czy użytkownik może otrzymać uprawnienia operatorskie.
- `mfa_enabled`: czy konto ma włączone MFA.
- `last_login_at`: ostatnie udane logowanie.
- `created_at`, `updated_at`.

Uwagi:

- `User` nie jest tenantem. Dostęp do zasobów tenantowych wynika z `OrganizationMember`.
- Konta operatorów platformy są nadal użytkownikami, ale ich uprawnienia operatorskie muszą być oddzielone od ról tenantowych.

### Organization

Reprezentuje klienta, firmę, zespół albo konto billingowe.

Kluczowe pola:

- `id`: UUID.
- `name`: nazwa organizacji.
- `slug`: unikalny identyfikator czytelny dla człowieka.
- `status`: `active`, `suspended`, `pending_deletion`, `deleted`.
- `billing_email`: adres do faktur i powiadomień billingowych.
- `owner_user_id`: użytkownik inicjalnie odpowiedzialny za organizację.
- `created_at`, `updated_at`, `deleted_at`.

Uwagi:

- `Organization` jest głównym tenant boundary dla danych biznesowych.
- Soft delete jest preferowany dla bezpieczeństwa audytu i integralności billingowej.

### OrganizationMember

Łączy użytkownika z organizacją i określa jego rolę w danej organizacji.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `user_id`: FK do `User`.
- `role_id`: FK do `Role`.
- `status`: `invited`, `active`, `disabled`, `removed`.
- `invited_by_user_id`: FK do `User`, nullable.
- `joined_at`, `created_at`, `updated_at`.

Uwagi:

- Jeden użytkownik może należeć do wielu organizacji.
- Członkostwo jest podstawą autoryzacji tenantowej.

### Role

Reprezentuje rolę przypisywaną członkowi organizacji albo operatorowi platformy.

Kluczowe pola:

- `id`: UUID.
- `scope`: `organization`, `project`, `platform`.
- `key`: np. `owner`, `admin`, `developer`, `viewer`, `platform_operator`.
- `name`: nazwa czytelna.
- `description`: opis roli.
- `is_system`: czy rola jest wbudowana.
- `created_at`, `updated_at`.

Uwagi:

- MVP zakłada role systemowe: `owner`, `admin`, `developer`, `viewer`.
- Role niestandardowe mogą pojawić się później, ale model nie powinien tego blokować.

### Permission

Reprezentuje atomowe uprawnienie wykorzystywane przez RBAC.

Kluczowe pola:

- `id`: UUID.
- `key`: np. `project.create`, `deployment.write`, `billing.manage`.
- `description`: opis uprawnienia.
- `category`: obszar funkcjonalny.
- `created_at`, `updated_at`.

Uwagi:

- Relacja `Role` -> `Permission` jest wiele-do-wielu.
- Backend powinien autoryzować operacje na podstawie permission keys, a nie nazw UI.

### Project

Reprezentuje aplikację lub stronę klienta zarządzaną w ramach organizacji.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `name`: nazwa projektu.
- `slug`: unikalny w organizacji.
- `status`: `active`, `suspended`, `pending_deletion`, `deleted`.
- `default_environment_id`: FK do `Environment`, nullable.
- `created_by_user_id`: FK do `User`.
- `created_at`, `updated_at`, `deleted_at`.

Uwagi:

- `Project` jest główną jednostką ownershipu dla deploymentów, domen, środowisk i runtime.
- W Kubernetes projekt zwykle mapuje się na namespace albo zestaw namespace per environment.

### Environment

Reprezentuje środowisko projektu, np. production, staging albo preview.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`.
- `name`: np. `production`, `staging`.
- `slug`: unikalny w projekcie.
- `type`: `production`, `staging`, `preview`, `development`.
- `status`: `active`, `suspended`, `deleted`.
- `kubernetes_namespace`: nazwa namespace przypisanego do środowiska.
- `created_at`, `updated_at`, `deleted_at`.

Uwagi:

- `organization_id` jest denormalizowany dla łatwiejszej filtracji tenantowej i indeksów.
- Namespace Kubernetes musi być unikalny globalnie.

### Deployment

Reprezentuje próbę wdrożenia konkretnej wersji aplikacji do środowiska.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`.
- `environment_id`: FK do `Environment`.
- `build_job_id`: FK do `BuildJob`, nullable.
- `version`: wersja lub numer deploymentu.
- `image_ref`: referencja obrazu kontenerowego.
- `status`: `queued`, `building`, `deploying`, `running`, `failed`, `rolled_back`, `cancelled`.
- `requested_by_user_id`: FK do `User`.
- `started_at`, `finished_at`, `created_at`, `updated_at`.

Uwagi:

- Deployment jest immutable w zakresie artefaktu i wersji po rozpoczęciu wdrażania.
- Zmiany statusu powinny emitować eventy domenowe.

### Domain

Reprezentuje domenę platformową albo własną domenę klienta przypisaną do projektu lub środowiska.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`.
- `environment_id`: FK do `Environment`.
- `hostname`: pełna nazwa hosta, canonical lowercase.
- `type`: `platform`, `custom`.
- `status`: `pending_verification`, `verified`, `active`, `failed`, `disabled`, `deleted`.
- `verification_token_hash`: hash tokenu DNS, nullable.
- `verified_at`: czas potwierdzenia własności.
- `created_at`, `updated_at`, `deleted_at`.

Uwagi:

- `hostname` musi być globalnie unikalny dla aktywnych domen.
- Routing nie może zostać aktywowany przed weryfikacją domeny.

### Certificate

Reprezentuje certyfikat TLS powiązany z domeną.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `domain_id`: FK do `Domain`.
- `provider`: np. `acme`.
- `status`: `pending`, `issued`, `renewing`, `failed`, `revoked`, `expired`.
- `not_before`, `not_after`.
- `serial_number_hash`: hash numeru seryjnego, jeśli przechowywany.
- `kubernetes_secret_name`: nazwa secretu TLS w Kubernetes.
- `last_error`: zredagowany opis błędu, nullable.
- `created_at`, `updated_at`.

Uwagi:

- Klucz prywatny certyfikatu nie powinien być przechowywany w bazie aplikacyjnej.
- Dane certyfikatu muszą być separowane per domain/project namespace.

### Subscription

Reprezentuje aktywną lub historyczną subskrypcję organizacji.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `plan_id`: FK do `Plan`.
- `stripe_customer_id`: identyfikator klienta Stripe.
- `stripe_subscription_id`: identyfikator subskrypcji Stripe.
- `status`: `trialing`, `active`, `past_due`, `unpaid`, `cancelled`, `incomplete`, `paused`.
- `current_period_start`, `current_period_end`.
- `cancel_at_period_end`: boolean.
- `created_at`, `updated_at`.

Uwagi:

- Stripe jest źródłem prawdy dla płatności i faktur.
- Lokalny `Subscription` jest zmaterializowanym stanem potrzebnym do autoryzacji limitów i funkcji.

### Plan

Reprezentuje ofertę produktową, limity i mapowanie na Stripe.

Kluczowe pola:

- `id`: UUID.
- `key`: np. `starter`, `team`, `enterprise`.
- `name`: nazwa planu.
- `status`: `active`, `archived`.
- `stripe_price_id`: identyfikator ceny w Stripe.
- `limits`: JSON z limitami projektów, środowisk, domen, CPU, RAM, storage, transferu, buildów.
- `features`: JSON lub relacja do flag funkcji.
- `created_at`, `updated_at`.

Uwagi:

- Plan nie należy do tenanta.
- Zmiana limitów planu wymaga audytu i testów zgodności z istniejącymi subskrypcjami.

### Invoice

Reprezentuje fakturę lub dokument rozliczeniowy zsynchronizowany ze Stripe.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `subscription_id`: FK do `Subscription`, nullable.
- `stripe_invoice_id`: identyfikator faktury Stripe.
- `status`: `draft`, `open`, `paid`, `void`, `uncollectible`.
- `amount_due`, `amount_paid`, `currency`.
- `hosted_invoice_url`: URL do faktury Stripe, nullable.
- `issued_at`, `paid_at`, `created_at`, `updated_at`.

Uwagi:

- Platforma nie przechowuje danych kart płatniczych.
- URL do faktury jest danymi wrażliwymi operacyjnie i wymaga autoryzacji.

### UsageRecord

Reprezentuje zagregowane zużycie zasobów dla organizacji, projektu, środowiska albo deploymentu.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`, nullable.
- `environment_id`: FK do `Environment`, nullable.
- `metric`: np. `cpu_seconds`, `memory_gb_hours`, `storage_gb_hours`, `egress_bytes`, `build_minutes`.
- `quantity`: wartość numeryczna.
- `unit`: jednostka.
- `period_start`, `period_end`.
- `source`: źródło meteringu.
- `created_at`.

Uwagi:

- Dane meteringowe powinny pochodzić z zaufanych źródeł infrastruktury, nie z workloadu klienta.
- Rekordy usage powinny być append-only albo korygowane przez jawne rekordy korekt.

### ApiKey

Reprezentuje klucz API używany przez integracje i automatyzację klienta.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`, nullable.
- `created_by_user_id`: FK do `User`.
- `name`: nazwa klucza.
- `prefix`: jawny prefiks identyfikacyjny.
- `key_hash`: hash sekretu API key.
- `scopes`: lista scope.
- `status`: `active`, `revoked`, `expired`.
- `last_used_at`, `expires_at`, `revoked_at`.
- `created_at`, `updated_at`.

Uwagi:

- Pełny sekret API key jest pokazywany tylko raz.
- Klucz musi mieć scope i tenant binding.

### AuditLog

Reprezentuje append-only dziennik operacji biznesowych i administracyjnych.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`, nullable dla operacji platformowych.
- `project_id`: FK do `Project`, nullable.
- `actor_user_id`: FK do `User`, nullable.
- `actor_type`: `user`, `api_key`, `system`, `operator`.
- `actor_ref`: zredagowany identyfikator aktora.
- `action`: np. `project.created`, `deployment.started`.
- `target_type`, `target_id`.
- `result`: `success`, `denied`, `failed`.
- `ip_address_hash`: hash IP, nullable.
- `user_agent_hash`: hash user agent, nullable.
- `correlation_id`.
- `metadata`: JSON bez sekretów.
- `created_at`.

Uwagi:

- Z perspektywy aplikacji rekordy nie mogą być aktualizowane ani usuwane.
- Audit log nie może zawierać pełnych tokenów, sekretów ani payloadów płatniczych.

### SecurityEvent

Reprezentuje zdarzenie bezpieczeństwa, które może wymagać alertu, reakcji albo korelacji.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`, nullable.
- `project_id`: FK do `Project`, nullable.
- `user_id`: FK do `User`, nullable.
- `severity`: `info`, `low`, `medium`, `high`, `critical`.
- `category`: np. `auth`, `rbac`, `rate_limit`, `stripe_webhook`, `kubernetes_policy`.
- `event_type`: szczegółowy typ zdarzenia.
- `source`: usługa źródłowa.
- `status`: `open`, `triaged`, `resolved`, `false_positive`.
- `correlation_id`.
- `metadata`: JSON bez sekretów.
- `created_at`, `resolved_at`.

Uwagi:

- `SecurityEvent` nie zastępuje `AuditLog`; służy do detekcji, triage i alertingu.

### BuildJob

Reprezentuje proces budowy obrazu kontenerowego albo przygotowania artefaktu deploymentu.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`.
- `environment_id`: FK do `Environment`, nullable.
- `requested_by_user_id`: FK do `User`.
- `source_type`: `upload`, `git`, `registry`.
- `source_ref`: zredagowana referencja źródła.
- `status`: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
- `image_ref`: wynikowy obraz, nullable.
- `sbom_ref`: referencja do SBOM, nullable.
- `logs_ref`: referencja do logów builda.
- `started_at`, `finished_at`, `created_at`, `updated_at`.

Uwagi:

- Build job wykonuje niezaufany kod i musi działać w izolowanym środowisku.
- Sekrety nie mogą być umieszczane w payloadzie joba ani logach.

### RuntimeInstance

Reprezentuje aktualny stan runtime w Kubernetes dla deploymentu, środowiska albo repliki aplikacji.

Kluczowe pola:

- `id`: UUID.
- `organization_id`: FK do `Organization`.
- `project_id`: FK do `Project`.
- `environment_id`: FK do `Environment`.
- `deployment_id`: FK do `Deployment`.
- `kubernetes_namespace`: namespace.
- `workload_name`: nazwa workloadu.
- `status`: `pending`, `running`, `degraded`, `failed`, `terminated`.
- `replica_count`: liczba replik.
- `last_observed_at`: czas ostatniej synchronizacji.
- `created_at`, `updated_at`.

Uwagi:

- Jest to zmaterializowany widok stanu runtime, a nie źródło prawdy dla konfiguracji.
- Synchronizacja musi być idempotentna.

### WebhookEvent

Reprezentuje przychodzące zdarzenie webhook z systemu zewnętrznego, np. Stripe.

Kluczowe pola:

- `id`: UUID.
- `provider`: np. `stripe`.
- `provider_event_id`: identyfikator eventu u providera.
- `event_type`: typ zdarzenia.
- `status`: `received`, `verified`, `processing`, `processed`, `failed`, `ignored`.
- `organization_id`: FK do `Organization`, nullable do czasu mapowania.
- `signature_valid`: boolean.
- `payload_hash`: hash payloadu.
- `received_at`, `processed_at`.
- `processing_attempts`: liczba prób.
- `last_error`: zredagowany opis błędu.
- `created_at`, `updated_at`.

Uwagi:

- Event musi być idempotentny po `provider` + `provider_event_id`.
- Pełny payload powinien być przechowywany tylko, jeśli istnieje uzasadnienie i spełnia wymagania retencji oraz redakcji danych.

## 3. Relacje

Relacje główne:

- `User` 1..N `OrganizationMember`.
- `Organization` 1..N `OrganizationMember`.
- `OrganizationMember` N..1 `Role`.
- `Role` N..M `Permission`.
- `Organization` 1..N `Project`.
- `Project` 1..N `Environment`.
- `Environment` 1..N `Deployment`.
- `BuildJob` 0..1 -> 1 `Deployment` jako źródło artefaktu deploymentu.
- `Project` 1..N `Domain`.
- `Environment` 1..N `Domain`.
- `Domain` 0..N `Certificate`, zwykle jeden aktywny certyfikat na domenę.
- `Organization` 0..N `Subscription`, zwykle jedna aktywna subskrypcja.
- `Plan` 1..N `Subscription`.
- `Subscription` 0..N `Invoice`.
- `Organization` 1..N `UsageRecord`.
- `Project` 0..N `UsageRecord`.
- `Organization` 1..N `ApiKey`.
- `Project` 0..N `ApiKey`.
- `Organization` 0..N `AuditLog`.
- `Organization` 0..N `SecurityEvent`.
- `Deployment` 0..N `RuntimeInstance`.
- `WebhookEvent` 0..1 `Organization` po rozpoznaniu providera i klienta.

Relacje ownershipu:

- `Organization` jest właścicielem: `Project`, `Subscription`, `Invoice`, `UsageRecord`, `ApiKey`, większości `AuditLog` i `SecurityEvent`.
- `Project` jest właścicielem: `Environment`, `Deployment`, `Domain`, `BuildJob`, `RuntimeInstance`.
- `Environment` zawęża kontekst runtime dla `Deployment`, `Domain` i `RuntimeInstance`.
- `Domain` jest właścicielem logicznym `Certificate`.
- `User` nie jest właścicielem projektów; użytkownik działa przez członkostwo w organizacji.

## 4. Zasady ownershipu

- Zasób tenantowy nie może istnieć bez `organization_id`, chyba że jest globalną konfiguracją platformy, np. `Plan`, `Role`, `Permission`.
- Zasób projektowy musi mieć zarówno `organization_id`, jak i `project_id`.
- `organization_id` w zasobach projektowych musi być zgodny z organizacją projektu.
- Zasób środowiskowy musi mieć `organization_id`, `project_id` i `environment_id`.
- `environment_id` musi wskazywać środowisko należące do tego samego projektu i organizacji.
- Użytkownik może wykonać operację na zasobie tenantowym tylko przez aktywne `OrganizationMember` albo uprawnienie operatorskie.
- Operacje operatorskie nie przenoszą ownershipu; są specjalnym trybem dostępu wymagającym audytu.
- Soft-deleted zasoby nie mogą być używane przez nowe operacje biznesowe, ale pozostają referencją dla audytu i historii.

## 5. Zasady multi-tenancy

- Tenant boundary to `Organization`.
- Project boundary to `Project`, a runtime boundary to `Environment`/namespace.
- Każdy endpoint API przyjmujący identyfikator zasobu musi potwierdzić, że zasób należy do aktywnej organizacji z kontekstu requestu.
- Listowania zasobów muszą zawsze filtrować po `organization_id`.
- Queryset bez tenant filter jest błędem bezpieczeństwa, chyba że dotyczy jawnie globalnej encji.
- Cache keys muszą zawierać `organization_id` i, gdy dotyczy, `project_id`.
- Joby asynchroniczne muszą zawierać minimalny tenant context i ponownie weryfikować stan zasobu przy wykonaniu.
- Dane logów, metryk i usage records muszą być separowane logicznie per organizacja/projekt.
- Publiczne identyfikatory powinny być UUID, aby ograniczyć enumerację.
- Błędy API nie mogą ujawniać istnienia zasobów innego tenanta.

## 6. Zasady autoryzacji

Model RBAC:

- `owner`: pełne zarządzanie organizacją, billingiem, członkami, projektami i API keys.
- `admin`: zarządzanie projektami, domenami, deploymentami i członkami bez operacji owner-only.
- `developer`: zarządzanie deploymentami, buildami, środowiskami technicznymi i odczyt logów projektu.
- `viewer`: odczyt konfiguracji, statusów, logów i metryk bez zmian.
- `platform_operator`: rola operatorska poza tenant RBAC, ograniczona przez osobne polityki i audyt.

Zasady:

- Uprawnienia są sprawdzane przez permission keys, np. `project.create`, `deployment.write`, `domain.verify`, `billing.manage`.
- Autoryzacja object-level jest obowiązkowa dla odczytu, zapisu, usuwania i operacji asynchronicznych.
- Operacje billingowe wymagają `billing.manage`.
- Operacje domenowe wymagają `domain.manage` i aktywnej subskrypcji, jeśli plan tego wymaga.
- Deployment wymaga `deployment.write`, aktywnego projektu, aktywnej organizacji i limitów planu.
- Odczyt logów wymaga `logs.read` oraz przynależności do projektu lub organizacji.
- Operacje operatora wymagają MFA, sesji operatorskiej, powodu dostępu i audit logu.
- API key może wykonać tylko akcje mieszczące się w jego scope i tenant binding.

## 7. Pola wrażliwe

Pola wymagające szczególnej ochrony:

- `User.password_hash`: zarządzany przez mechanizmy Django, nigdy nie logować.
- Dane MFA użytkownika: przechowywać szyfrowane poza publicznym modelem użytkownika.
- `User.email`: dane osobowe, ograniczać ekspozycję i logowanie.
- `Organization.billing_email`: dane osobowe i billingowe.
- `ApiKey.key_hash`: hash sekretu, pełny sekret nigdy nie jest przechowywany.
- `ApiKey.prefix`: jawny tylko jako identyfikator, nie sekret.
- `Domain.verification_token_hash`: hash tokenu, nie plain text.
- `Certificate.kubernetes_secret_name`: wrażliwa informacja operacyjna, nie eksponować szeroko.
- Klucze prywatne certyfikatów: nie przechowywać w bazie aplikacyjnej.
- `Subscription.stripe_customer_id`, `stripe_subscription_id`: identyfikatory billingowe, ograniczać ekspozycję.
- `Invoice.hosted_invoice_url`: dostęp tylko dla uprawnionych użytkowników.
- `WebhookEvent.payload_hash` i ewentualny payload: nie przechowywać danych kart ani sekretów.
- `AuditLog.ip_address_hash`, `user_agent_hash`: dane pseudonimizowane.
- `BuildJob.source_ref`, `logs_ref`, `image_ref`: mogą ujawniać strukturę repozytorium lub registry.
- `RuntimeInstance.kubernetes_namespace`, `workload_name`: informacje operacyjne, ograniczać w API publicznym.
- `AuditLog.metadata`, `SecurityEvent.metadata`: wymagają walidacji i redakcji sekretów.

## 8. Indeksy bazy

Indeksy podstawowe:

- `User(email)` unikalny case-insensitive.
- `Organization(slug)` unikalny dla aktywnych organizacji.
- `OrganizationMember(organization_id, user_id)` unikalny dla aktywnego członkostwa.
- `OrganizationMember(user_id, status)`.
- `Role(scope, key)` unikalny.
- `Permission(key)` unikalny.
- `Project(organization_id, slug)` unikalny dla aktywnych projektów.
- `Project(organization_id, status)`.
- `Environment(project_id, slug)` unikalny dla aktywnych środowisk.
- `Environment(kubernetes_namespace)` unikalny.
- `Deployment(environment_id, created_at DESC)`.
- `Deployment(organization_id, project_id, status)`.
- `Domain(hostname)` unikalny dla aktywnych domen.
- `Domain(organization_id, project_id, status)`.
- `Certificate(domain_id, status)`.
- `Certificate(not_after)` dla monitoringu expiry.
- `Subscription(organization_id, status)`.
- `Subscription(stripe_subscription_id)` unikalny, nullable-safe.
- `Subscription(stripe_customer_id)`.
- `Plan(key)` unikalny.
- `Plan(stripe_price_id)` unikalny dla aktywnych planów.
- `Invoice(stripe_invoice_id)` unikalny.
- `Invoice(organization_id, issued_at DESC)`.
- `UsageRecord(organization_id, period_start, period_end)`.
- `UsageRecord(project_id, metric, period_start)`.
- `ApiKey(prefix)` unikalny.
- `ApiKey(organization_id, status)`.
- `AuditLog(organization_id, created_at DESC)`.
- `AuditLog(project_id, created_at DESC)`.
- `AuditLog(actor_user_id, created_at DESC)`.
- `AuditLog(correlation_id)`.
- `SecurityEvent(severity, status, created_at DESC)`.
- `SecurityEvent(organization_id, created_at DESC)`.
- `BuildJob(organization_id, project_id, status)`.
- `BuildJob(created_at DESC)`.
- `RuntimeInstance(environment_id, status)`.
- `RuntimeInstance(kubernetes_namespace, workload_name)` unikalny dla aktywnych instancji.
- `WebhookEvent(provider, provider_event_id)` unikalny.
- `WebhookEvent(status, received_at)`.

Uwagi:

- Dla soft delete należy stosować partial unique indexes, np. unikalność tylko gdy `deleted_at IS NULL`.
- Indeksy po `created_at DESC` są istotne dla listowania historii i audytu.
- Indeksy tenantowe muszą wspierać najczęstsze filtry autoryzacji.

## 9. Ograniczenia integralności

Ograniczenia wymagane:

- `OrganizationMember.organization_id + user_id` unikalne dla aktywnych członkostw.
- Każda organizacja musi mieć co najmniej jednego aktywnego `owner`; usunięcie ostatniego ownera jest niedozwolone.
- `Project.organization_id` musi odpowiadać organizacji wskazanej przez wszystkie zależne zasoby.
- `Environment.project_id` musi należeć do tej samej `organization_id`.
- `Deployment.environment_id` musi należeć do tego samego `project_id` i `organization_id`.
- `Domain.environment_id` musi należeć do tego samego `project_id` i `organization_id`.
- Aktywna domena custom musi mieć `verified_at`.
- `Domain.hostname` musi być canonical lowercase i unikalny globalnie dla aktywnych domen.
- Aktywny certyfikat musi wskazywać aktywną albo zweryfikowaną domenę.
- Jedna organizacja może mieć tylko jedną aktywną subskrypcję standardową, chyba że model enterprise jawnie to rozszerzy.
- `Subscription.plan_id` musi wskazywać aktywny albo historycznie zachowany plan.
- `WebhookEvent(provider, provider_event_id)` musi być unikalny dla idempotencji.
- `ApiKey.key_hash` musi być niepusty, a pełny sekret nie może być przechowywany.
- `AuditLog` i historyczne `WebhookEvent` nie powinny być usuwane przez zwykłe operacje aplikacyjne.
- Statusy muszą przechodzić tylko dozwolonymi przejściami, np. `Deployment.queued -> building -> deploying -> running`.
- `UsageRecord.period_start < period_end`.
- `Invoice.amount_due`, `amount_paid` i `UsageRecord.quantity` nie mogą być ujemne.

Ograniczenia aplikacyjne:

- Usunięcie organizacji wymaga wcześniejszego zawieszenia projektów i usunięcia aktywnego routingu domen.
- Zawieszona organizacja nie może tworzyć nowych projektów, domen, deploymentów ani API keys.
- Projekt `suspended` nie może przyjmować nowych deploymentów, ale może pozwalać na odczyt danych i logów zgodnie z polityką.
- Plan limits muszą być sprawdzane przed operacjami kosztowymi.

## 10. Eventy domenowe

Eventy powinny być emitowane przez warstwę domenową po transakcyjnym zapisie stanu. Dla integracji asynchronicznych preferowany jest outbox pattern.

Podstawowe eventy:

- `user.registered`
- `user.email_verified`
- `user.mfa_enabled`
- `organization.created`
- `organization.suspended`
- `organization.reactivated`
- `organization.deleted`
- `organization_member.invited`
- `organization_member.joined`
- `organization_member.role_changed`
- `project.created`
- `project.suspended`
- `project.deleted`
- `environment.created`
- `build_job.queued`
- `build_job.started`
- `build_job.succeeded`
- `build_job.failed`
- `deployment.requested`
- `deployment.started`
- `deployment.succeeded`
- `deployment.failed`
- `deployment.rolled_back`
- `domain.added`
- `domain.verification_requested`
- `domain.verified`
- `domain.activated`
- `domain.disabled`
- `certificate.requested`
- `certificate.issued`
- `certificate.renewal_failed`
- `subscription.created`
- `subscription.plan_changed`
- `subscription.past_due`
- `subscription.cancelled`
- `invoice.created`
- `invoice.paid`
- `invoice.payment_failed`
- `usage_record.recorded`
- `api_key.created`
- `api_key.revoked`
- `webhook_event.received`
- `webhook_event.processed`
- `security_event.detected`
- `audit_log.recorded`

Zasady eventów:

- Event nie może zawierać sekretów.
- Event musi zawierać `event_id`, `event_type`, `occurred_at`, `organization_id` jeśli dotyczy, `actor` jeśli dotyczy i `correlation_id`.
- Konsumenci eventów muszą być idempotentni.
- Eventy billingowe i provisioningowe muszą być odporne na retry.

## 11. Przykładowe przepływy

### Utworzenie organizacji

1. Użytkownik z potwierdzonym e-mailem wysyła request utworzenia organizacji.
2. Backend waliduje nazwę, slug i limity konta użytkownika.
3. W transakcji powstaje `Organization` ze statusem `active`.
4. Tworzony jest `OrganizationMember` dla użytkownika z rolą `owner`.
5. Opcjonalnie tworzony jest `Subscription` w stanie `incomplete` albo rozpoczynany checkout Stripe.
6. Emitowane są eventy `organization.created` i `organization_member.joined`.
7. Zapisywany jest `AuditLog` dla utworzenia organizacji.
8. Jeśli wymagany jest billing, użytkownik jest kierowany do Stripe Checkout albo ekranu wyboru planu.

Kontrole bezpieczeństwa:

- rate limit na tworzenie organizacji;
- audit event z aktorem;
- brak możliwości utworzenia organizacji dla nieaktywnego użytkownika;
- brak zaufania do roli przekazanej przez klienta.

### Utworzenie projektu

1. Użytkownik wybiera aktywną organizację.
2. Backend sprawdza `project.create` dla użytkownika w tej organizacji.
3. Backend sprawdza status organizacji i limity planu.
4. W transakcji powstaje `Project`.
5. Tworzone jest domyślne `Environment`, zwykle `production`.
6. Orchestrator otrzymuje zadanie utworzenia namespace i bazowych polityk Kubernetes.
7. Emitowane są eventy `project.created` i `environment.created`.
8. Zapisywany jest `AuditLog`.

Kontrole bezpieczeństwa:

- `organization_id` pochodzi z kontekstu autoryzacji;
- slug projektu jest unikalny tylko w organizacji;
- namespace Kubernetes jest generowany przez system, nie przez użytkownika;
- job asynchroniczny ponownie sprawdza, czy projekt nadal istnieje i jest aktywny.

### Deployment

1. Użytkownik lub API key żąda deploymentu dla projektu i środowiska.
2. Backend sprawdza `deployment.write`, status organizacji, status projektu, status subskrypcji i limity planu.
3. Jeśli wymagany jest build, tworzony jest `BuildJob` ze statusem `queued`.
4. Worker build uruchamia izolowany build i zapisuje wynikowy `image_ref`.
5. Po sukcesie builda tworzony albo aktualizowany jest `Deployment` ze statusem `deploying`.
6. Deployment orchestrator tworzy lub aktualizuje zasoby Kubernetes w namespace środowiska.
7. Synchronizator runtime aktualizuje `RuntimeInstance`.
8. Po gotowości workloadu `Deployment` przechodzi do `running`.
9. Emitowane są eventy `build_job.*`, `deployment.*` i zapisywane są audit logi.

Kontrole bezpieczeństwa:

- build działa bez sekretów platformy i z limitami zasobów;
- obraz jest skanowany przed wdrożeniem zgodnie z polityką;
- orchestrator używa minimalnego RBAC;
- workload nie może naruszać polityk Kubernetes;
- retry deploymentu jest idempotentny.

### Dodanie domeny

1. Użytkownik żąda dodania domeny do projektu i środowiska.
2. Backend sprawdza `domain.manage`, status projektu, status subskrypcji i limity domen w planie.
3. Backend normalizuje hostname do canonical lowercase i sprawdza globalną unikalność aktywnej domeny.
4. Tworzony jest `Domain` ze statusem `pending_verification`.
5. Generowany jest token weryfikacyjny, a w bazie zapisywany jest tylko jego hash.
6. Użytkownik konfiguruje rekord DNS.
7. Worker weryfikacji sprawdza DNS i ustawia `verified_at` oraz status `verified`.
8. Po weryfikacji certificate service tworzy `Certificate` i żąda certyfikatu ACME.
9. Po wydaniu certyfikatu domena może przejść do `active`, a ingress routing zostaje włączony.
10. Emitowane są eventy `domain.*` i `certificate.*`, a operacje trafiają do `AuditLog`.

Kontrole bezpieczeństwa:

- domena nie routuje ruchu przed weryfikacją;
- aktywny `hostname` jest globalnie unikalny;
- token weryfikacyjny nie jest przechowywany plain text;
- błędy ACME i DNS nie ujawniają sekretów ani szczegółów innych tenantów.

### Zmiana planu

1. Owner organizacji wybiera nowy plan.
2. Backend sprawdza `billing.manage` oraz status organizacji.
3. Backend inicjuje zmianę w Stripe albo tworzy checkout/customer portal session.
4. Stripe wysyła webhook o zmianie subskrypcji.
5. Endpoint webhook weryfikuje podpis i zapisuje `WebhookEvent`.
6. Worker przetwarza event idempotentnie i aktualizuje `Subscription.plan_id`, status oraz okres rozliczeniowy.
7. Backend wykonuje reconciliation krytycznych pól ze Stripe API, jeśli wymagane.
8. Emitowany jest event `subscription.plan_changed`.
9. Zapisywany jest audit log z aktorem i źródłem zmiany.

Kontrole bezpieczeństwa:

- lokalny plan nie zmienia się wyłącznie na podstawie niezaufanego requestu z UI;
- webhook jest weryfikowany podpisem i idempotentny;
- mapowanie `stripe_customer_id` do organizacji jest unikalne i testowane;
- zmiana limitów nie usuwa automatycznie danych klienta.

### Blokada po nieudanej płatności

1. Stripe wysyła webhook `invoice.payment_failed` albo zmianę subskrypcji na `past_due`/`unpaid`.
2. Endpoint webhook weryfikuje podpis i zapisuje `WebhookEvent`.
3. Worker przetwarza event idempotentnie i aktualizuje `Invoice` oraz `Subscription.status`.
4. Jeśli polityka grace period została przekroczona, organizacja przechodzi do `suspended` albo ograniczonego trybu.
5. Nowe deploymenty, domeny, buildy i API keys są blokowane.
6. Istniejące workloady mogą pozostać aktywne lub zostać zawieszone zgodnie z polityką produktu.
7. Użytkownicy z uprawnieniem `billing.manage` otrzymują powiadomienie.
8. Emitowane są eventy `invoice.payment_failed`, `subscription.past_due` i `organization.suspended`.
9. Zapisywane są audit logi i security event, jeśli blokada wygląda jak abuse albo fraud.

Kontrole bezpieczeństwa:

- blokada jest wynikiem zaufanego stanu Stripe, nie samego requestu użytkownika;
- operacje po blokadzie sprawdzają status organizacji po stronie serwera;
- odblokowanie wymaga potwierdzonego eventu Stripe albo decyzji operatora z audytem;
- API keys organizacji respektują zawieszenie przy każdej autoryzacji.
