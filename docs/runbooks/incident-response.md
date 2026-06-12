# Runbook: Incident Response

## Cel

Ten runbook definiuje bazową procedurę obsługi incydentów bezpieczeństwa i dostępności platformy SaaS. Stosujemy go dla incydentów dotyczących control plane, dashboardu, API, runtime aplikacji klientów, billing, domen, certyfikatów, storage, bazy danych i łańcucha dostaw.

## Severity Levels

| Severity | Definicja | Przykłady | Cel reakcji |
| --- | --- | --- | --- |
| SEV1 Critical | Aktywny incydent z istotnym wpływem na poufność, integralność lub dostępność wielu tenantów albo danych osobowych. | wyciek danych, masowy IDOR, przejęcie klucza produkcyjnego, awaria bazy produkcyjnej | incident commander w 15 min, containment natychmiast |
| SEV2 High | Poważny wpływ na jednego lub kilku tenantów, brak dowodu masowej eskalacji, wysoki potencjał szkód. | przejęcie konta admina, awaria Stripe webhooków, malware w buildzie, krytyczna podatność zależności | triage w 30 min, containment w 60 min |
| SEV3 Medium | Ograniczony wpływ, workaround dostępny, niskie ryzyko dalszej eskalacji. | pojedynczy błąd deploymentu, certyfikat wygasa, częściowa awaria storage | triage w 4 h |
| SEV4 Low | Zdarzenie bez aktywnego wpływu produkcyjnego, wymaga poprawki lub monitoringu. | fałszywy alert, niekrytyczna luka, pojedynczy błąd klienta | obsługa w normalnym backlogu |

## Role I Odpowiedzialności

- Incident Commander: prowadzi incydent, ustala severity, decyduje o containment, pilnuje osi czasu.
- Security Lead: ocenia wpływ na poufność, integralność, dane osobowe, klucze i obowiązki notyfikacyjne.
- Engineering Lead: koordynuje fix, rollback, hotfix i testy regresyjne.
- Operations Lead: obsługuje infrastrukturę, Kubernetes, backup/restore, DNS, storage i monitoring.
- Communications Lead: przygotowuje komunikaty do klientów, status page, supportu i interesariuszy.
- Scribe: prowadzi timeline, decyzje, hipotezy, dowody i linki do logów.

Jedna osoba może pełnić kilka ról w małym incydencie, ale SEV1/SEV2 wymaga jawnego właściciela dla każdej roli.

## Minimalne Logi Do Analizy

- `request_id` / `correlation_id` dla żądań API, webhooków, tasków Celery, deploymentów i provisioningu.
- `actor_type`, `actor_id`, `organization_id`, `project_id`, `action`, `target_type`, `target_id` z AuditLog.
- IP address, user agent, session id hash, API key prefix, role i scopes.
- Statusy `Deployment`, `BuildJob`, `RuntimeInstance`, `Domain`, `Certificate`, `Subscription`, `WebhookEvent`.
- Logi access/API gateway, Django, Celery, provisioner-service, deployment-worker, Stripe webhook handler.
- Metryki Prometheus: error rate, latency, queue depth, task duration, DB latency, storage usage.
- Kubernetes events, audit logs, pod logs, network policy denials.
- Dla security: alerty SAST/dependency scanning/container scanning, malware scan, image digest, SBOM.

Nigdy nie kopiujemy do ticketów ani czatów: haseł, tokenów sesyjnych, pełnych API keys, recovery codes, prywatnych kluczy, pełnych payloadów webhooków zawierających dane wrażliwe.

## Checklist Pierwszych 30 Minut

1. Utwórz incident channel i ticket incydentu.
2. Wyznacz Incident Commander, Security Lead, Engineering Lead, Operations Lead, Communications Lead i Scribe.
3. Ustal wstępny severity i zakres: tenant, projekt, region, komponent, czas rozpoczęcia.
4. Zamroź istotne logi i snapshoty metryk; zabezpiecz `request_id`, `correlation_id`, artefakty buildów i AuditLog.
5. Zatrzymaj automatyczne retry lub deploymenty, jeśli zwiększają szkody.
6. Wykonaj pierwszy containment: revoke key, disable account, block domain, pause worker, rollback, rate limit, network block.
7. Sprawdź, czy incydent dotyczy danych osobowych lub danych wielu tenantów.
8. Przygotuj pierwszy komunikat wewnętrzny: co wiemy, czego nie wiemy, kto prowadzi, następna aktualizacja.
9. Jeśli SEV1/SEV2, przygotuj status page lub customer notice, nawet jeśli jest to tylko informacja o badaniu problemu.
10. Zapisz timeline od pierwszego alertu do obecnej decyzji.

## Procedury Incydentów

### Wyciek Danych

- Wykrycie: alert DLP, nietypowy eksport danych, zgłoszenie klienta, anomalie AuditLog, logi wskazujące cross-tenant access.
- Klasyfikacja: SEV1, jeśli obejmuje dane osobowe, sekrety, dane wielu tenantów albo publiczną ekspozycję; SEV2 dla ograniczonego wycieku jednego tenanta.
- Triage: określ typ danych, tenantów, czas ekspozycji, aktora, endpointy, request ids, czy dane zostały pobrane.
- Ograniczenie szkód: wyłącz podatny endpoint, zablokuj klucze/sesje, odetnij publiczny dostęp, zatrzymaj eksporty, zachowaj dowody.
- Komunikacja: Security Lead ocenia obowiązki prawne; Communications Lead przygotowuje komunikat dla klientów i supportu.
- Naprawa: hotfix, test regresyjny, rotacja sekretów, poprawka filtrów tenancy, walidacja logów i danych.
- Postmortem: pełny timeline, root cause, zakres danych, opóźnienia detekcji, skuteczność containment.
- Prewencja: rozszerz testy IDOR, alerty na masowe odczyty, DLP, przegląd uprawnień i retencję logów.

### Podejrzenie Przejęcia Konta

- Wykrycie: nietypowe logowanie, impossible travel, wiele błędnych 2FA, zmiana e-maila/hasła, zgłoszenie użytkownika.
- Klasyfikacja: SEV2 dla admina/ownera/operatora; SEV3 dla zwykłego użytkownika bez szkód.
- Triage: sprawdź sesje, IP, user agent, role, ostatnie AuditLog, zmiany API keys i billing.
- Ograniczenie szkód: unieważnij sesje, wymuś reset hasła i 2FA, tymczasowo zablokuj konto, odbierz role wysokiego ryzyka.
- Komunikacja: poinformuj właściciela organizacji; nie ujawniaj szczegółów atakującemu kanałowi.
- Naprawa: przywróć role, cofnij nieautoryzowane zmiany, rotuj klucze utworzone w oknie incydentu.
- Postmortem: ustal wektor, brakujące alerty, czy 2FA było wymagane i egzekwowane.
- Prewencja: mocniejsze reguły risk-based auth, alerty logowania, wymuszenie 2FA dla ról uprzywilejowanych.

### Przejęcie API Key

- Wykrycie: anomalie usage, żądania z nowych IP, przekroczenia rate limit, klucz widoczny w repo/logach/tickecie.
- Klasyfikacja: SEV2 dla klucza organizacyjnego lub scope wysokiego ryzyka; SEV3 dla klucza projektowego o niskim scope.
- Triage: ustal prefix klucza, scopes, project/organization, ostatnie `last_used_at`, działania wysokiego ryzyka.
- Ograniczenie szkód: revoke key, zatrzymaj powiązane deploymenty, rotuj zależne sekrety, dodaj blokady IP/rate limit.
- Komunikacja: poinformuj ownerów organizacji i support o wymaganej rotacji.
- Naprawa: utwórz nowy klucz, zweryfikuj scope, odtwórz legalne integracje klienta.
- Postmortem: gdzie klucz wyciekł, czy pełny klucz pojawił się poza jednorazowym widokiem.
- Prewencja: secret scanning, krótsze expiration, scope minimalny, alerty nietypowego użycia.

### Błędna Autoryzacja / IDOR

- Wykrycie: test security, zgłoszenie klienta, logi 404/403 nietypowe, AuditLog pokazuje dostęp do obcego `organization_id`.
- Klasyfikacja: SEV1 dla cross-tenant read/write; SEV2 dla ograniczonego endpointu bez danych wrażliwych.
- Triage: znajdź endpoint, parametry, queryset, helpery tenancy, role, konkretne obiekty i czas ekspozycji.
- Ograniczenie szkód: wyłącz endpoint, dodaj feature flag block, ogranicz routing/API gateway, cofnij nieuprawnione zmiany.
- Komunikacja: komunikuj zakres dopiero po potwierdzeniu tenantów i typów danych.
- Naprawa: filtruj przez organization context, użyj `get_object_for_organization_or_404`, dodaj test regresyjny.
- Postmortem: dlaczego review/testy IDOR nie złapały luki.
- Prewencja: wzorce bezpiecznych querysetów, linters/checklisty code review, testy per endpoint i per rola.

### Awaria Stripe Webhooków

- Wykrycie: rosnące `WebhookEvent.failed`, alert Stripe, brak aktualizacji subskrypcji/faktur, błędy podpisu.
- Klasyfikacja: SEV2, jeśli wpływa na billing wielu tenantów; SEV3 dla opóźnień bez utraty danych.
- Triage: sprawdź signature secret, event ids, statusy retry, idempotency, kolejki i błędy Stripe API.
- Ograniczenie szkód: zatrzymaj automatyczne blokady kont, replay webhooków tylko po idempotency check, nie ufaj danym z frontendu.
- Komunikacja: poinformuj finance/support o opóźnieniach billingowych.
- Naprawa: napraw secret/config, przetwórz zaległe eventy, uzgodnij lokalny stan Subscription/Invoice ze Stripe.
- Postmortem: utracone eventy, opóźnienie detekcji, skuteczność idempotencji.
- Prewencja: dashboard webhook lag, alert na failed ratio, testy replay i invalid signature.

### Awaria Deploymentów

- Wykrycie: failed deployments, wzrost task failures, build timeout, brak aktywnego RuntimeInstance.
- Klasyfikacja: SEV2 dla globalnej awarii deploy; SEV3 dla pojedynczych projektów.
- Triage: sprawdź BuildJob, Deployment, worker logs, registry, Kubernetes namespace, resource quotas.
- Ograniczenie szkód: wstrzymaj nowe deploymenty, rollback do ostatniej aktywnej wersji, zatrzymaj wadliwy worker.
- Komunikacja: status page dla globalnej awarii; klientowi podaj project/deployment id i workaround.
- Naprawa: hotfix worker/provisioner, odblokuj registry, popraw limity, replay deploymentów.
- Postmortem: etap awarii, brakujący probe/alert, czy rollback był skuteczny.
- Prewencja: canary worker, testy pipeline, alert na failure rate, limity czasu i retry backoff.

### Przejęcie Domeny

- Wykrycie: domena wskazuje na obcy projekt, konflikt domen, zmiana DNS, zgłoszenie właściciela domeny.
- Klasyfikacja: SEV1, jeśli ruch użytkowników trafia do złego tenanta; SEV2 dla pending takeover bez aktywnego ruchu.
- Triage: sprawdź token TXT, Domain owner, organization, project, ingress, cert, historię AuditLog.
- Ograniczenie szkód: disable domain, usuń ingress, wstrzymaj cert request, zablokuj ponowne dodanie do wyjaśnienia.
- Komunikacja: komunikuj tylko zweryfikowanym ownerom organizacji i właścicielowi domeny.
- Naprawa: wymuś ponowną weryfikację TXT, usuń błędne mapowania, odtwórz cert i ingress.
- Postmortem: czy token był hash/fresh, czy blokada duplikatów zadziałała.
- Prewencja: krótkie TTL tokenów, audyt domen systemowych, alerty na konflikty i zmiany DNS.

### Błąd Certyfikatu SSL

- Wykrycie: `Certificate.failed`, `expired`, ACME error, alert cert expiring, zgłoszenie TLS.
- Klasyfikacja: SEV2 dla wielu domen/systemowej domeny; SEV3 dla pojedynczej domeny klienta.
- Triage: sprawdź DNS, CAA, cert-manager CertificateRequest/Order/Challenge, rate limits ACME.
- Ograniczenie szkód: utrzymaj ostatni działający ingress, wyłącz domenę tylko przy ryzyku bezpieczeństwa.
- Komunikacja: informuj klienta o wymaganych zmianach DNS lub statusie odnowienia.
- Naprawa: retry cert request, popraw issuer, odtwórz DNS, przełącz na fallback issuer jeśli dopuszczony.
- Postmortem: dlaczego alert nie wyprzedził expiracji.
- Prewencja: alert 14/7/3 dni, syntetyczne testy TLS, runbook `certificate-failure.md`.

### Atak DDoS

- Wykrycie: wzrost request count, latency, 5xx, bandwidth, WAF/CDN alert, queue saturation.
- Klasyfikacja: SEV1 dla niedostępności platformy; SEV2 dla ataku na jednego tenanta bez wpływu globalnego.
- Triage: określ target, źródła, warstwę L3/L4/L7, endpointy, tenant, koszt zasobów.
- Ograniczenie szkód: WAF/CDN challenge, rate limit, blokady IP/ASN/country, izolacja tenanta, autoscaling kontrolowany.
- Komunikacja: status page dla wpływu globalnego; support script dla klientów.
- Naprawa: usuń hot endpoint bottleneck, cache, tune limits, przywróć normalny routing.
- Postmortem: skuteczność WAF, koszty, progi alertów, czas reakcji.
- Prewencja: CDN/WAF baseline, per-tenant quotas, rate limiting, testy obciążeniowe.

### Nadużycie Platformy Przez Klienta

- Wykrycie: abuse reports, malware/phishing, spam, DDoS outbound, naruszenie ToS, nietypowy transfer.
- Klasyfikacja: SEV2, jeśli szkodzi innym klientom lub reputacji platformy; SEV3 dla izolowanego naruszenia.
- Triage: zbierz domeny, projekty, deploymenty, ownerów, logi egress, zgłoszenia zewnętrzne.
- Ograniczenie szkód: suspend project/domain, throttle egress, disable deployment, zachowaj dowody.
- Komunikacja: legal/support kontaktuje klienta zgodnie z ToS; nie ujawniaj danych zgłaszających bez potrzeby.
- Naprawa: przywróć usługę po usunięciu treści i zatwierdzeniu przez abuse ownera.
- Postmortem: czy polityki wykrywania i limity były wystarczające.
- Prewencja: abuse monitoring, egress limits, domain reputation checks, malware scanning.

### Wykrycie Malware W Buildzie

- Wykrycie: image scan, dependency scan, malware scanner, suspicious build behavior.
- Klasyfikacja: SEV2, jeśli obraz został uruchomiony; SEV3, jeśli blokada nastąpiła przed deployem.
- Triage: image digest, BuildJob, source ref, dependency, severity, czy runtime był aktywny.
- Ograniczenie szkód: zablokuj deployment, usuń obraz z registry albo oznacz denylist, zatrzymaj runtime.
- Komunikacja: poinformuj klienta o blokadzie i wymaganych zmianach.
- Naprawa: rebuild po usunięciu malware, ponowny scan, aktualizacja polityki skanowania.
- Postmortem: czy scanner miał aktualne sygnatury i czy blokada działała.
- Prewencja: mandatory scan before deploy, SBOM, denylist digestów, izolacja build namespace.

### Podatność Krytyczna W Zależności

- Wykrycie: dependency scanning, CVE advisory, SAST/SCA, vendor alert.
- Klasyfikacja: SEV1, jeśli exploit jest aktywny i komponent publiczny; SEV2 dla krytycznej zależności bez exploitacji.
- Triage: wersja, komponent, exposure, exploitability, dostępny fix, SBOM, tenant impact.
- Ograniczenie szkód: wyłącz podatną funkcję, WAF rule, ogranicz endpoint, przyspiesz patch.
- Komunikacja: security advisory dla klientów, jeśli wpływ jest potwierdzony.
- Naprawa: upgrade, test regresyjny, redeploy, rebuild obrazów, rescanning.
- Postmortem: czas od advisory do patcha, braki w pinning/CI.
- Prewencja: dependency bot, SCA w CI, SBOM, polityka maksymalnego czasu patchowania.

### Awaria Bazy Danych

- Wykrycie: DB latency, connection errors, failed migrations, replication lag, storage full.
- Klasyfikacja: SEV1 dla niedostępności control plane; SEV2 dla degradacji lub repliki.
- Triage: primary/replica status, ostatnie migracje, locks, slow queries, disk, backup freshness.
- Ograniczenie szkód: zatrzymaj write-heavy workers, przełącz read-only jeśli możliwe, zablokuj migracje.
- Komunikacja: status page dla degradacji API/dashboardu.
- Naprawa: failover, restore staging/recovery, rollback migracji tylko po analizie, odtwórz indeksy.
- Postmortem: RPO/RTO, przyczyna awarii, czy backup był odtwarzalny.
- Prewencja: DB alerts, migration safety, regular restore test, capacity planning.

### Awaria Storage

- Wykrycie: błędy S3/MinIO, failed uploads, brak artefaktów deploymentu, wzrost 5xx dla static assets.
- Klasyfikacja: SEV1 dla utraty danych lub globalnej niedostępności artefaktów; SEV2 dla degradacji.
- Triage: bucket, prefix, tenant impact, object count, provider status, IAM credentials, recent deletes.
- Ograniczenie szkód: zablokuj delete/overwrite, przełącz na read-only, zatrzymaj deploymenty zapisujące do storage.
- Komunikacja: poinformuj klientów z aktywnym wpływem na serving lub deployment.
- Naprawa: restore z backupu, resync obiektów, rotacja credentials, napraw IAM/bucket policy.
- Postmortem: utrata danych, RPO/RTO, brakujące alerty, skuteczność retencji.
- Prewencja: versioning object storage, lifecycle protection, backup test, per-prefix least privilege.

## Postmortem Standard

Każdy SEV1/SEV2 wymaga postmortem w ciągu 5 dni roboczych. Dokument musi zawierać: streszczenie, impact, timeline, root cause, detection gap, containment, co zadziałało, co nie zadziałało, działania naprawcze z ownerami i terminami, testy regresyjne oraz decyzję, czy wymagana jest komunikacja zewnętrzna.
