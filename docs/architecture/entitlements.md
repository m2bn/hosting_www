# Billing-service i entitlements

## 1. Cel

Billing-service odpowiada za lokalny model planów, subskrypcji, faktur i webhooków Stripe. Entitlements odpowiadają za jedną, centralną odpowiedź na pytanie: czy organizacja albo projekt może wykonać kosztowną akcję.

Endpointy nie liczą limitów samodzielnie. Każdy endpoint biznesowy pyta moduł `apps/api/entitlements.py`.

## 2. Model planów

`Plan` definiuje kod planu w polu `key`, nazwę w `name`, opcjonalny `stripe_price_id` oraz dwa kontrakty JSON:

- `limits`: limity ilościowe;
- `features`: flagi funkcjonalne.

Obsługiwane limity:

- `projects`: maksymalna liczba aktywnych projektów;
- `storage_gb`: limit storage;
- `transfer_gb`: limit transferu;
- `runtime_cpu_millicores`: limit CPU runtime;
- `runtime_memory_mb`: limit RAM runtime.

Obsługiwane funkcje:

- `custom_domains`: możliwość używania własnych domen;
- `container_deployments`: możliwość deploymentów kontenerowych.

Brak wartości limitu albo wartość `unlimited` oznacza brak limitu dla danego wymiaru. Brak flagi funkcjonalnej oznacza `False`.

## 3. Plany bazowe

Aktualnie zakładamy trzy klasy planów:

- `free`: niski limit projektów, storage i transferu, bez custom domains i bez container deployments;
- `pro`: wyższe limity, custom domains i container deployments włączone;
- `business`: wysokie limity runtime, storage i transferu, custom domains i container deployments włączone.

Konkretne wartości limitów są konfigurowane rekordem `Plan`, a nie kodem endpointu.

## 4. Status subskrypcji

`Subscription` należy do `Organization` i wskazuje `Plan`.

Statusy:

- `incomplete`: subskrypcja nieaktywna, blokuje tworzenie zasobów i deploymenty;
- `trialing`: działa jak aktywna subskrypcja;
- `active`: pełny dostęp zgodnie z planem;
- `past_due`: dostęp możliwy tylko w grace period;
- `canceled`: blokuje tworzenie zasobów i deploymenty;
- `unpaid`: blokuje tworzenie zasobów i deploymenty.

Dla zgodności z wcześniejszym modelem akceptowana jest też wartość `cancelled`, traktowana jak `canceled`.

## 5. Brak subskrypcji

Domyślna polityka to `ENTITLEMENTS_NO_SUBSCRIPTION_POLICY = "free"`, czyli organizacja bez subskrypcji dostaje bezpieczny zestaw Free.

Możliwa jest polityka `deny`, w której brak subskrypcji blokuje akcje kosztowe. Produkcyjna decyzja powinna być jawna w konfiguracji środowiska.

## 6. Funkcje centralne

Moduł `apps/api/entitlements.py` udostępnia:

- `can_create_project(organization)`;
- `can_add_domain(organization)`;
- `can_deploy_project(project)`;
- `can_use_custom_domain(organization)`;
- `can_use_container_deployment(organization)`;
- `get_project_limit(organization)`;
- `get_storage_limit(organization)`;
- `get_transfer_limit(organization)`;
- `get_runtime_limits(project)`.

Funkcje decyzyjne zwracają `EntitlementDecision` z polami:

- `allowed`;
- `reason`;
- `code`;
- `metadata`.

Kod wywołujący powinien opierać decyzję wyłącznie na `allowed`; `reason`, `code` i `metadata` służą do odpowiedzi API, logów i testów.

## 7. Webhooki Stripe

`WebhookEvent` przechowuje eventy Stripe idempotentnie przez unikalność `(provider, provider_event_id)`.

Docelowy handler Stripe powinien:

- zweryfikować podpis webhooka przed zmianą stanu;
- zapisać hash payloadu, nie pełne dane wrażliwe;
- utworzyć albo zaktualizować `WebhookEvent`;
- wykonywać operacje idempotentnie;
- aktualizować `Subscription` i `Invoice` w transakcji;
- zapisać `AuditLog` dla zmian billingowych.

## 8. Zasady bezpieczeństwa

- Endpointy nie mogą liczyć limitów ani sprawdzać planów bezpośrednio.
- Endpointy nie mogą ufać planowi ani limitom przekazanym w request body.
- `past_due` ma ograniczony grace period przez `ENTITLEMENTS_PAST_DUE_GRACE_DAYS`.
- `canceled`, `cancelled`, `unpaid` i `incomplete` blokują tworzenie nowych zasobów i deploymenty.
- Organizacja z anulowaną albo nieopłaconą subskrypcją nie może automatycznie spaść do Free i ominąć blokady.
- Brak subskrypcji używa Free albo deny-by-default wyłącznie przez jawną konfigurację.
- Dane Stripe traktujemy jako dane zewnętrzne: webhook musi być podpisany, idempotentny i odporny na replay.

## 9. Testy wymagane

Każda zmiana entitlementów musi mieć testy dla:

- planów `free`, `pro`, `business`;
- statusów `active`, `trialing`, `past_due`, `canceled`, `unpaid`;
- przekroczenia limitu projektów;
- przekroczenia limitu storage;
- przekroczenia limitu transferu;
- braku subskrypcji;
- integracji endpointu z centralnym `can_*`, bez lokalnego liczenia limitów.
