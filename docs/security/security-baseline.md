# Security baseline platformy SaaS

## 1. Cel dokumentu

Ten dokument definiuje minimalny baseline bezpieczeństwa dla multi-tenant platformy SaaS do hostingu stron i aplikacji klientów. Baseline jest obowiązkowy dla MVP produkcyjnego i ma być stosowany przy projektowaniu, implementacji, testowaniu oraz odbiorze każdego modułu.

OWASP ASVS Level 2 jest bazą wymagań. Oznacza to, że system ma być projektowany i testowany z założeniem ochrony przed typowymi i umiarkowanie zaawansowanymi atakami na aplikacje webowe, API, sesje, kontrolę dostępu, dane, logi, konfigurację i integracje. Decyzje architektoniczne nie mogą blokować późniejszego przejścia do OWASP ASVS Level 3.

## 2. Zasady ogólne

- Bezpieczeństwo jest wymaganiem funkcjonalnym, a nie późniejszym dodatkiem.
- Każdy request, webhook, plik, artefakt, obraz kontenerowy i workload klienta jest traktowany jako niezaufany do momentu walidacji i autoryzacji.
- Każda operacja musi mieć jawny kontekst tenanta: organizację, projekt albo uzasadniony kontekst administracyjny.
- Domyślna polityka dostępu to deny-by-default.
- Uprawnienia użytkowników, usług, operatorów i workloadów muszą być minimalne.
- Granice control plane i data plane muszą być technicznie egzekwowane.
- Dane tenantów nie mogą mieszać się w API, bazie, cache, logach, metrykach, backupach ani runtime.
- Każda operacja bezpieczeństwa musi być testowalna.

## 3. OWASP ASVS Level 2

Platforma musi spełniać OWASP ASVS Level 2 w obszarach istotnych dla systemu:

- architektura, threat modeling i secure design;
- uwierzytelnianie użytkowników, administratorów i usług;
- zarządzanie sesją;
- kontrola dostępu;
- walidacja wejścia, obsługa plików i ochrona przed injection;
- kryptografia i zarządzanie sekretami;
- obsługa błędów, logowanie i audyt;
- ochrona danych osobowych i danych tenantów;
- komunikacja sieciowa i TLS;
- konfiguracja bezpieczeństwa;
- API, webhooki i integracje zewnętrzne;
- upload plików i przetwarzanie niezaufanych artefaktów;
- CI/CD, zależności i supply chain.

Dla każdego modułu wymagane jest mapowanie najważniejszych decyzji bezpieczeństwa do ASVS L2 lub świadome opisanie wyjątku. Wyjątki muszą mieć właściciela, datę rewizji, ocenę ryzyka i plan domknięcia.

## 4. Tożsamość i uwierzytelnianie

- Konta użytkowników muszą wymagać weryfikacji adresu e-mail.
- Hasła muszą być hashowane algorytmem odpornym na GPU, takim jak Argon2id lub bcrypt z właściwymi parametrami.
- Reset hasła musi używać jednorazowych, krótkotrwałych tokenów.
- Token resetu hasła nie może ujawniać, czy konto istnieje.
- Logowanie musi być chronione rate limitingiem i detekcją credential stuffing.
- Konta administracyjne i operatorskie muszą mieć obowiązkowe 2FA/MFA.
- 2FA dla administratorów musi być egzekwowane po stronie serwera, nie tylko w UI.
- Zmiana hasła, włączenie lub wyłączenie 2FA, zmiana e-maila i reset MFA muszą emitować audit event.
- Dla operacji wysokiego ryzyka należy stosować step-up authentication.

## 5. Bezpieczne sesje

- Sesje webowe muszą używać cookies z flagami `HttpOnly`, `Secure` i `SameSite`.
- Identyfikator sesji musi być generowany kryptograficznie bezpiecznie.
- Identyfikator sesji musi być rotowany po logowaniu, podniesieniu uprawnień, zmianie hasła i zmianie konfiguracji MFA.
- Sesje muszą mieć maksymalny czas życia oraz idle timeout.
- Użytkownik musi mieć możliwość unieważnienia aktywnych sesji.
- Wylogowanie musi unieważniać sesję po stronie serwera.
- Tokeny sesyjne nie mogą być przechowywane w `localStorage`.
- Mutacje wykonywane przez cookie-based auth muszą mieć ochronę CSRF.
- API używane przez integracje powinno korzystać z API keys lub tokenów maszynowych, a nie z sesji użytkownika.
- Sesje administracyjne powinny mieć krótsze TTL niż sesje zwykłych użytkowników.

## 6. RBAC i kontrola dostępu

- Autoryzacja musi być egzekwowana po stronie serwera dla każdego endpointu i joba asynchronicznego.
- UI nie jest mechanizmem bezpieczeństwa i nie może być jedyną warstwą kontroli dostępu.
- Role MVP: `owner`, `admin`, `developer`, `viewer`.
- Role operatorów platformy muszą być oddzielone od ról tenantów.
- Każde uprawnienie musi być oceniane w kontekście organizacji i projektu.
- Endpointy listujące zasoby muszą filtrować po tenant context.
- Endpointy operujące na zasobie muszą sprawdzać, czy zasób należy do organizacji/projektu użytkownika.
- Operacje administracyjne muszą wymagać osobnych uprawnień operatorskich i pełnego audytu.
- API keys muszą mieć scope, ownera, tenant binding, datę utworzenia, opcjonalny expiry i możliwość odwołania.
- Testy autoryzacji cross-tenant są obowiązkowe dla każdego modułu.

## 7. Rate limiting i abuse protection

- Public API musi mieć rate limiting per IP, użytkownik, organizacja i API key.
- Endpointy logowania, resetu hasła, rejestracji, zaproszeń i 2FA muszą mieć ostrzejsze limity.
- Webhooki i endpointy integracyjne muszą mieć limity chroniące przed floodem.
- Operacje kosztowe, takie jak deployment, build, upload, generowanie certyfikatów i eksport logów, muszą mieć limity per organizacja/projekt.
- Rate limiting musi zwracać bezpieczne odpowiedzi bez ujawniania nadmiarowych szczegółów.
- Limity muszą być monitorowane i audytowane przy przekroczeniach istotnych bezpieczeństwowo.
- Dla MVP należy mieć możliwość ręcznego zablokowania użytkownika, organizacji, projektu, API key lub źródłowego IP.

## 8. Security headers i ochrona przeglądarki

Web App i Admin Console muszą ustawiać co najmniej:

- `Content-Security-Policy` z ograniczeniem źródeł skryptów, stylów, ramek i połączeń;
- `Strict-Transport-Security` dla domen produkcyjnych;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy`;
- `Frame-Options` albo odpowiednik w CSP przez `frame-ancestors`;
- `Permissions-Policy`;
- bezpieczne nagłówki cache dla stron i odpowiedzi zawierających dane wrażliwe.

Dodatkowe wymagania:

- Panel platformy nie może serwować uploadowanych plików z tej samej domeny, jeśli pliki mogą zawierać aktywną treść.
- Logi i dane klientów muszą być renderowane jako tekst, chyba że użyto sprawdzonej sanitizacji.
- CSP violations powinny być monitorowane w środowisku produkcyjnym.

## 9. Szyfrowanie sekretów i rotacja kluczy

- Sekrety nie mogą być przechowywane w kodzie, repozytorium, obrazach kontenerowych ani logach.
- Sekrety muszą być przechowywane w dedykowanym secret store albo szyfrowane z użyciem KMS.
- Sekrety aplikacyjne w bazie danych muszą być szyfrowane envelope encryption albo równoważnym mechanizmem.
- Klucze szyfrujące muszą mieć właściciela, cel, datę utworzenia i procedurę rotacji.
- Rotacja kluczy musi być możliwa bez pełnego przestoju platformy.
- Dostęp do sekretów musi być audytowany.
- Sekrety klientów muszą być separowane per organizacja/projekt.
- Sekrety platformy nie mogą być dostępne z workloadów klientów.
- API keys muszą być przechowywane jako hash, a pełny sekret może być pokazany użytkownikowi tylko raz.
- Procedura incident response musi opisywać rotację sekretów po wycieku.

## 10. Least privilege

- Każda usługa control plane musi mieć osobne konto usługowe.
- Konta usługowe muszą mieć minimalne uprawnienia do bazy, kolejki, cache, secret store, Kubernetes API, Stripe i DNS.
- Dostęp operatorów do produkcji musi być minimalny, czasowy i audytowany.
- Workloady klientów nie mogą mieć dostępu do Kubernetes API, control plane ani sekretów platformy.
- Builder obrazów nie może mieć stałego dostępu do produkcyjnych sekretów.
- CI/CD nie może udostępniać sekretów niezaufanym pull requestom.
- Uprawnienia muszą być regularnie przeglądane.
- Break-glass access musi być jawny, monitorowany i rozliczalny.

## 11. Audyt zdarzeń

Audit log musi obejmować co najmniej:

- logowanie, wylogowanie, błędne próby logowania i reset hasła;
- włączenie, wyłączenie i reset 2FA;
- tworzenie, usuwanie i modyfikację organizacji, projektów, ról i członkostw;
- tworzenie, odwołanie i użycie API keys dla operacji wrażliwych;
- zmiany billing state, planów i statusów subskrypcji;
- przetwarzanie webhooków Stripe;
- dodanie, weryfikację, usunięcie i rewalidację domen;
- wydanie, odnowienie i błędy certyfikatów SSL;
- deploymenty, rollbacki, zawieszenie i usunięcie workloadów;
- uploady i buildy artefaktów;
- operacje administracyjne i operatorskie;
- dostęp do logów, danych osobowych, backupów i sekretów;
- zmiany konfiguracji bezpieczeństwa.

Wymagania techniczne:

- Audit log musi być append-only z perspektywy aplikacji.
- Audit event musi zawierać czas, aktora, tenant context, typ akcji, wynik, źródło i korelację requestu.
- Audit log nie może zawierać sekretów ani pełnych tokenów.
- Usunięcie użytkownika nie może usuwać historycznych audit eventów; dane osobowe należy pseudonimizować zgodnie z polityką retencji.
- Dostęp do audit logu musi być kontrolowany i audytowany.

## 12. Separacja tenantów

- Każdy request musi być powiązany z jednym tenant context albo z jawnie oznaczoną operacją platformową.
- Dane tenantów muszą być separowane w bazie przez obowiązkowy identyfikator organizacji/projektu i kontrolę dostępu.
- Cache keys, kolejki, joby asynchroniczne, obiekty storage i metryki muszą być namespacowane tenantem.
- Logi i metryki dostępne klientowi muszą być filtrowane per organizacja/projekt.
- Backupy muszą mieć kontrolę dostępu i procedury odtwarzania ograniczające ryzyko pomieszania tenantów.
- Błędy API nie mogą ujawniać istnienia zasobów innych tenantów.
- Testy cross-tenant muszą obejmować odczyt, zapis, listowanie, usuwanie i operacje asynchroniczne.

## 13. Polityki Kubernetes

MVP musi egzekwować następujące wymagania dla workloadów klientów:

- namespace per projekt lub środowisko projektu;
- oddzielne service accounty per projekt;
- minimalne Kubernetes RBAC;
- `ResourceQuota` i `LimitRange`;
- deny-by-default `NetworkPolicy`;
- brak dostępu do control plane i usług administracyjnych;
- brak kontenerów `privileged`;
- brak `hostPath`, `hostNetwork`, `hostPID` i `hostIPC`;
- ograniczone Linux capabilities;
- `runAsNonRoot` tam, gdzie możliwe;
- seccomp profile ustawiony na `RuntimeDefault` albo równoważny;
- read-only root filesystem tam, gdzie aplikacja to wspiera;
- zakaz dostępu do socketu runtime kontenerowego;
- polityki admission blokujące zasoby niezgodne z baseline;
- skanowanie obrazów przed wdrożeniem;
- monitoring anomalii runtime i przekroczeń limitów.

Komponenty control plane uruchamiane w Kubernetes muszą mieć ostrzejszy profil bezpieczeństwa niż workloady klientów i nie mogą współdzielić service accountów z tenant runtime.

## 14. Backup i restore

- Backupy bazy danych, konfiguracji, audit logów i krytycznych obiektów muszą być automatyczne.
- Backupy muszą być szyfrowane z użyciem KMS lub równoważnego mechanizmu.
- Dostęp do backupów musi być ograniczony i audytowany.
- Publiczny dostęp do storage backupów musi być technicznie zablokowany.
- Backupy muszą mieć retencję zgodną z wymaganiami biznesowymi, prawnymi i kosztowymi.
- Restore musi być testowany cyklicznie na środowisku izolowanym.
- Procedura restore musi obejmować RPO, RTO, właścicieli, kroki techniczne i kryteria walidacji.
- Restore danych jednego tenanta nie może nadpisać danych innego tenanta.
- Backup sekretów musi zachowywać wymagania rotacji i szyfrowania.
- Usuwanie danych musi uwzględniać retencję backupów i wymagania prywatności.

## 15. Wymagania dla logów

- Logi nie mogą zawierać sekretów, tokenów, haseł, pełnych API keys, pełnych payloadów płatniczych ani danych kart.
- Dane osobowe w logach muszą być minimalizowane i maskowane tam, gdzie to możliwe.
- Każdy log aplikacyjny powinien mieć correlation id, request id, tenant context i service name.
- Logi bezpieczeństwa muszą odróżniać sukces, odmowę dostępu, błąd walidacji i błąd systemowy.
- Logi klientów muszą być separowane logicznie per projekt i dostępne tylko uprawnionym użytkownikom.
- Logi muszą mieć zdefiniowaną retencję i limity kosztowe.
- Logi muszą być chronione przed nieautoryzowaną modyfikacją.
- Logi nie mogą być jedynym źródłem audit trail dla operacji wrażliwych.
- System musi mieć secret scanning logów lub równoważny mechanizm wykrywania wycieków.

## 16. Wymagania dla monitoringu

Monitoring musi obejmować:

- dostępność Web App, Public API, Admin Console i krytycznych usług control plane;
- błędy autoryzacji, logowania, 2FA i sesji;
- rate limiting, abuse signals i anomalie ruchu;
- kolejki, joby provisioningowe, deploymenty i buildy;
- Kubernetes API, nody, namespace, quota, pody i ingress;
- certyfikaty SSL, błędy ACME i czas do wygaśnięcia certyfikatów;
- webhooki Stripe, błędy podpisu, retry i opóźnienia;
- bazę danych, cache, event bus, secret store i KMS;
- log ingestion, metering i koszty obserwowalności;
- backupy, wyniki restore testów i błędy retencji;
- zdarzenia operatorskie i administracyjne wysokiego ryzyka.

Alerty muszą mieć właściciela, priorytet, runbook i kryteria eskalacji. Alerty bezpieczeństwa muszą obejmować co najmniej: wiele błędnych logowań, podejrzane operacje cross-tenant, użycie break-glass, błędy webhooków Stripe, wygasające certyfikaty, naruszenia polityk Kubernetes, wykrycie sekretu w logach oraz nietypowy wzrost kosztów lub zużycia.

## 17. Wymagania dla CI/CD

- CI/CD musi uruchamiać testy jednostkowe, integracyjne i krytyczne testy bezpieczeństwa.
- Pull request nie może zostać scalony, jeśli łamie testy autoryzacji, sesji, tenant isolation albo polityki Kubernetes.
- Pipeline musi wykonywać SAST, dependency scanning i secret scanning.
- Obrazy kontenerowe muszą być skanowane przed publikacją.
- Zależności i obrazy bazowe muszą być pinowane do wersji lub digestów tam, gdzie to możliwe.
- Pipeline musi generować SBOM dla komponentów platformy.
- Sekrety CI/CD muszą być dostępne tylko dla zaufanych branchy i środowisk.
- Deployment produkcyjny musi być powtarzalny, audytowalny i możliwy do wycofania.
- Migracje bazy danych muszą być testowane przed produkcją.
- Zmiany infrastruktury i polityk Kubernetes muszą przechodzić policy-as-code.
- Artefakty release muszą być identyfikowalne do commita, builda i autora zatwierdzenia.
- Krytyczne podatności w zależnościach lub obrazach muszą blokować release, chyba że istnieje zatwierdzony wyjątek ryzyka.

## 18. Definition of Secure Done

Ta checklista obowiązuje dla każdego modułu, endpointu, joba, integracji i komponentu infrastruktury. Moduł nie jest gotowy, dopóki wymagane punkty nie są spełnione albo nie mają zaakceptowanego wyjątku ryzyka.

### Projekt i model zagrożeń

- [ ] Moduł ma opisany zakres odpowiedzialności i granice zaufania.
- [ ] Zidentyfikowano aktywa przetwarzane przez moduł.
- [ ] Zidentyfikowano najważniejsze scenariusze STRIDE dla modułu.
- [ ] Wymagania OWASP ASVS Level 2 właściwe dla modułu są spełnione albo mają udokumentowany wyjątek.
- [ ] Dane wejściowe, wyjściowe i zależności zewnętrzne są jawnie opisane.

### Uwierzytelnianie, sesje i autoryzacja

- [ ] Każdy endpoint i job asynchroniczny wymaga właściwego uwierzytelnienia albo ma jawnie udokumentowany powód publiczności.
- [ ] Każda operacja ma serwerową autoryzację w kontekście organizacji, projektu lub operatora.
- [ ] Testy obejmują próby dostępu cross-tenant.
- [ ] Role i scope API keys są minimalne.
- [ ] Operacje wysokiego ryzyka wymagają MFA, step-up auth albo dodatkowej kontroli.

### Walidacja danych i odporność na abuse

- [ ] Wszystkie dane wejściowe są walidowane po stronie serwera.
- [ ] Identyfikatory zasobów są sprawdzane pod kątem właścicielstwa tenantowego.
- [ ] Pola URL są odporne na SSRF.
- [ ] Upload plików ma limity, walidację typu i bezpieczne przechowywanie.
- [ ] Operacje kosztowe mają rate limiting, quota albo backpressure.
- [ ] Błędy nie ujawniają danych innych tenantów ani szczegółów infrastruktury.

### Dane, sekrety i prywatność

- [ ] Moduł nie loguje sekretów, tokenów, haseł ani pełnych API keys.
- [ ] Dane osobowe są minimalizowane i mają uzasadniony cel przetwarzania.
- [ ] Sekrety są przechowywane w secret store/KMS albo szyfrowane zgodnie z baseline.
- [ ] Klucze i sekrety mają procedurę rotacji.
- [ ] Dane tenantów są separowane w bazie, cache, storage, logach i metrykach.
- [ ] Retencja danych jest określona.

### Audyt, logi i monitoring

- [ ] Operacje zmieniające stan emitują audit event.
- [ ] Operacje wrażliwe emitują audit event z aktorem, tenant context, wynikiem i correlation id.
- [ ] Logi mają correlation id, tenant context i nazwę usługi.
- [ ] Moduł ma metryki techniczne i bezpieczeństwa.
- [ ] Istnieją alerty dla awarii i nadużyć właściwych dla modułu.
- [ ] Dostęp do logów i danych diagnostycznych jest autoryzowany.

### Kubernetes i infrastruktura

- [ ] Workload działa z minimalnymi uprawnieniami.
- [ ] Workload nie używa `privileged`, `hostPath`, `hostNetwork`, `hostPID` ani nadmiarowych capabilities.
- [ ] Zdefiniowano limity CPU, RAM i storage.
- [ ] Zdefiniowano NetworkPolicy lub uzasadniono wyjątek.
- [ ] Service account ma minimalne RBAC.
- [ ] Sekrety nie są wypiekane w obrazie kontenerowym.

### CI/CD i release

- [ ] Moduł ma testy jednostkowe i integracyjne dla krytycznych ścieżek.
- [ ] Moduł ma testy negatywne bezpieczeństwa dla autoryzacji, walidacji i izolacji tenantów.
- [ ] SAST, dependency scanning i secret scanning przechodzą bez krytycznych wyników.
- [ ] Obraz kontenerowy przechodzi skan podatności albo ma zaakceptowany wyjątek.
- [ ] Zmiany infrastruktury przechodzą policy-as-code.
- [ ] Release jest audytowalny i możliwy do wycofania.

### Dokumentacja i operacje

- [ ] Moduł ma opisane wymagania operacyjne, limity i zależności.
- [ ] Istnieje runbook dla awarii lub incydentów związanych z modułem.
- [ ] Backup i restore są uwzględnione, jeśli moduł przechowuje dane trwałe.
- [ ] Właściciel modułu jest wskazany.
- [ ] Znane ryzyka i wyjątki są zapisane w backlogu bezpieczeństwa.
