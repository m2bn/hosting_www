# Wizja architektury platformy SaaS do hostingu stron i aplikacji

## 1. Cele systemu

Platforma ma umożliwiać bezpieczne, powtarzalne i skalowalne hostowanie stron oraz aplikacji klientów w modelu multi-tenant SaaS. System powinien wspierać pełny cykl życia projektu klienta: utworzenie organizacji, konfigurację projektu, wdrożenie aplikacji, podpięcie domeny, automatyczne wystawienie certyfikatu SSL, obserwowalność, billing oraz audyt działań.

Główne cele:

- zapewnić izolację tenantów na poziomie danych, uprawnień, runtime i sieci;
- umożliwić uruchamianie aplikacji klientów w Kubernetes w sposób kontrolowany i limitowany;
- zbudować fundament zgodny z OWASP ASVS Level 2, bez decyzji blokujących późniejsze przejście do Level 3;
- zapewnić przejrzysty model użytkowników, organizacji, projektów, ról i uprawnień;
- zintegrować billing subskrypcyjny i rozliczanie zużycia zasobów;
- zapewnić automatyczną obsługę domen własnych oraz certyfikatów TLS;
- dostarczyć audytowalne operacje administracyjne i użytkownika;
- umożliwić monitoring, alerting, metering i diagnostykę problemów produkcyjnych;
- utrzymać architekturę modularną, aby komponenty control plane, billing, runtime i observability mogły rozwijać się niezależnie.

## 2. Zakres MVP produkcyjnego

MVP produkcyjny obejmuje minimalny, ale bezpieczny i operowalny zakres funkcji potrzebny do obsługi pierwszych klientów.

Zakres funkcjonalny:

- konta użytkowników z logowaniem, resetem hasła i weryfikacją adresu e-mail;
- organizacje, członkostwa, role podstawowe: owner, admin, developer, viewer;
- projekty przypisane do organizacji;
- panel zarządzania organizacją, projektami, domenami, deploymentami i billingiem;
- integracja ze Stripe dla subskrypcji, statusu płatności, faktur i webhooków;
- podstawowy lifecycle projektu: create, configure, deploy, suspend, delete;
- uruchamianie aplikacji klientów w Kubernetes jako odseparowane workloady;
- automatyczna konfiguracja ingressu i certyfikatów TLS dla domen platformowych oraz własnych domen klientów;
- podstawowy metering CPU, RAM, storage, transferu i liczby deploymentów;
- logi aplikacyjne dostępne per projekt z kontrolą dostępu;
- audyt operacji użytkowników i administracji;
- monitoring infrastruktury i aplikacji platformy;
- alerting dla incydentów krytycznych;
- backup danych platformy i procedura odtwarzania;
- administracyjne narzędzia do blokowania organizacji, projektu lub deploymentu.

Zakres bezpieczeństwa MVP:

- zgodność projektowa z OWASP ASVS Level 2 dla obszarów uwierzytelniania, sesji, kontroli dostępu, walidacji wejścia, logowania, konfiguracji i ochrony danych;
- MFA dla kont administracyjnych i opcjonalnie dla użytkowników organizacji;
- centralny model autoryzacji dla API i panelu;
- separacja danych tenantów w warstwie aplikacyjnej i bazodanowej;
- izolacja workloadów klientów przez namespace, NetworkPolicy, limity zasobów, security context i odrębne service accounty;
- bezpieczna obsługa webhooków Stripe z weryfikacją podpisów;
- szyfrowanie danych w tranzycie;
- szyfrowanie sekretów i zarządzanie nimi poza kodem aplikacji;
- podstawowy proces vulnerability management dla obrazów kontenerów i zależności.

## 3. Zakres docelowy

Zakres docelowy rozszerza MVP o funkcje skalowania, automatyzacji, zgodności i zaawansowanej izolacji.

Docelowe możliwości:

- zaawansowany RBAC z rolami niestandardowymi i uprawnieniami per projekt;
- SSO/SAML/OIDC dla organizacji enterprise;
- wymuszanie MFA oraz polityki bezpieczeństwa per organizacja;
- pełna historia deploymentów, rollbacki i środowiska typu production, preview, staging;
- integracje z repozytoriami Git i automatyczne deploymenty z pipeline;
- builder obrazów lub bezpieczny system przyjmowania artefaktów;
- autoscaling workloadów klientów;
- regionalizacja infrastruktury i wybór regionu projektu;
- izolacja wybranych tenantów w dedykowanych node poolach lub klastrach;
- zaawansowany metering i usage-based billing;
- budżety, limity i alerty kosztowe per organizacja;
- self-service export logów, metryk i audit trail;
- WAF, ochrona przed DDoS i reguły bezpieczeństwa per domena;
- pełniejsza zgodność z OWASP ASVS Level 3 dla klientów wymagających wyższego poziomu zaufania;
- formalny program secure SDLC, threat modeling, testy penetracyjne i okresowe audyty;
- mechanizmy data residency i retencji danych per organizacja;
- private networking, statyczne adresy egress i integracje z prywatnymi zasobami klientów;
- marketplace lub katalog template'ów aplikacji.

## 4. Komponenty systemu

### Control plane

Control plane zarządza użytkownikami, organizacjami, projektami, konfiguracją deploymentów, domenami, certyfikatami, billingiem oraz stanem runtime. Jest źródłem prawdy dla konfiguracji platformy.

Podstawowe elementy:

- Web App: panel użytkownika i administratora;
- Public API: API dla panelu, CLI i integracji;
- Auth Service: uwierzytelnianie, sesje, tokeny, MFA;
- Authorization/RBAC Service: ocena uprawnień użytkownika względem organizacji i projektu;
- Tenant/Organization Service: organizacje, członkostwa, zaproszenia i role;
- Project Service: projekty, konfiguracje, statusy i limity;
- Deployment Orchestrator: zamiana konfiguracji projektu na zasoby Kubernetes;
- Domain Service: weryfikacja domen, rekordy DNS, status propagacji;
- Certificate Service: integracja z cert-manager/ACME i obsługa odnowień;
- Billing Service: plany, subskrypcje, limity, status płatności;
- Metering Service: agregacja zużycia zasobów;
- Audit Log Service: niezmienialny dziennik działań;
- Notification Service: e-mail, alerty użytkownika i komunikaty systemowe;
- Admin Console: narzędzia operacyjne dla zespołu platformy.

### Data plane

Data plane uruchamia aplikacje klientów i obsługuje ruch do nich.

Podstawowe elementy:

- Kubernetes Cluster: runtime workloadów klientów;
- Namespace per projekt lub per środowisko projektu;
- Ingress Controller/Gateway: terminacja TLS i routing HTTP(S);
- cert-manager: automatyczne certyfikaty TLS;
- External DNS lub integracja DNS: automatyzacja rekordów platformowych, gdzie możliwa;
- Container Registry: przechowywanie obrazów aplikacji klientów;
- Runtime Policies: Pod Security Admission, NetworkPolicy, ResourceQuota, LimitRange;
- Secrets Operator: bezpieczne dostarczanie sekretów do workloadów;
- Log Collector: zbieranie logów aplikacji i platformy;
- Metrics Collector: Prometheus/OpenTelemetry lub równoważny system;
- Object Storage: artefakty, backupy, logi długoterminowe.

### Warstwa danych

Warstwa danych przechowuje stan platformy i dane operacyjne.

Podstawowe elementy:

- Relational Database: użytkownicy, organizacje, projekty, billing state, konfiguracja;
- Audit Log Store: append-only lub technicznie wzmacniany model niezmienialności;
- Metrics Store: dane meteringowe i monitoringowe;
- Logs Store: logi aplikacyjne i systemowe;
- Cache/Queue: Redis lub równoważny system dla sesji pomocniczych, kolejek i rate limitingu;
- Event Bus/Queue: asynchroniczne zdarzenia billingowe, provisioningowe i notyfikacyjne;
- Secret Store/KMS: klucze, sekrety i materiały kryptograficzne.

### Integracje zewnętrzne

- Stripe: subskrypcje, faktury, płatności, podatki, webhooki;
- ACME CA: wystawianie certyfikatów TLS;
- DNS Provider: automatyzacja DNS dla domen platformowych;
- Email Provider: wiadomości transakcyjne;
- Observability/Incident Tooling: alerting i on-call;
- Container/Image Scanner: skanowanie podatności obrazów;
- Git Provider w zakresie docelowym.

## 5. Granice zaufania

Najważniejsze granice zaufania:

- Browser użytkownika -> Public API: ruch niezaufany, wymagane TLS, CSRF protection dla cookie-based auth, walidacja wejścia, rate limiting i kontrola sesji.
- Public API -> Control Plane Services: ruch wewnętrzny, wymagane uwierzytelnienie usługowe, autoryzacja operacji i propagacja kontekstu audytowego.
- Control Plane -> Database/Secret Store: dostęp wyłącznie przez kontrolowane service accounty, minimalne uprawnienia i szyfrowanie.
- Control Plane -> Kubernetes API: bardzo wysoka wrażliwość; wymagane least privilege, dedykowane service accounty i polityki ograniczające operacje.
- Kubernetes Control Plane -> Tenant Workloads: tenant workloady są niezaufane; nie mogą wpływać na control plane ani inne tenanty.
- Tenant Workload -> Internet: ruch wychodzący kontrolowany politykami egress tam, gdzie to możliwe.
- Internet -> Ingress/Gateway -> Tenant Workload: publiczny ruch niezaufany, wymagane izolowane routowanie, limity i ochrona przed nadużyciami.
- Stripe -> Billing Webhook Endpoint: ruch zewnętrzny, wymagane weryfikowanie podpisów, idempotencja i odporność na replay.
- ACME/DNS Provider -> Domain/Certificate Services: zewnętrzne systemy z ograniczonym zaufaniem, wymagane bezpieczne przechowywanie tokenów API.
- Admin Console -> Platform Operations: najwyższy poziom ryzyka; wymagane MFA, silny RBAC, pełny audyt i osobne uprawnienia administracyjne.
- Logs/Metrics/Audit Stores -> Users/Admins: dane mogą zawierać informacje wrażliwe; wymagane filtrowanie tenantów, maskowanie sekretów i kontrola dostępu.

Założenie bazowe: aplikacje klientów, dane wejściowe klientów, obrazy kontenerów klientów i ruch publiczny są traktowane jako niezaufane.

## 6. Główne ryzyka techniczne

- Złożoność izolacji w Kubernetes: błędna konfiguracja namespace, RBAC, NetworkPolicy lub security context może prowadzić do wpływu jednego tenanta na innych.
- Spójność stanu między control plane a Kubernetes: awarie częściowe mogą powodować rozjazd między stanem zapisanym w bazie a realnymi zasobami.
- Automatyczne SSL i domeny własne: propagacja DNS, limity ACME, błędne rekordy i odnowienia certyfikatów mogą generować awarie widoczne dla klientów.
- Billing i metering: niedokładne pomiary zużycia albo błędy w synchronizacji ze Stripe mogą prowadzić do strat finansowych i sporów z klientami.
- Skalowanie logów i metryk: duża liczba tenantów może szybko zwiększyć koszt i złożoność przechowywania danych obserwowalności.
- Noisy neighbor: workload jednego klienta może zużywać zasoby współdzielone i pogarszać jakość usługi innym klientom.
- Migracje danych i konfiguracji: zmiany modelu tenantów, projektów i billing state będą trudne po wejściu na produkcję.
- Zarządzanie sekretami: sekrety platformy i klientów muszą być rotowalne, audytowalne i odseparowane.
- Incident response: bez dobrych runbooków i korelacji zdarzeń diagnoza awarii multi-tenant będzie wolna.
- Koszty infrastruktury: automatyzacja deploymentów bez twardych limitów może generować niekontrolowane koszty.

## 7. Główne ryzyka bezpieczeństwa

- Broken Access Control między organizacjami, projektami lub rolami.
- Tenant data leakage przez błędy w zapytaniach, cache, logach, metrykach lub storage.
- Ucieczka z kontenera albo eskalacja uprawnień workloadu klienta w klastrze.
- SSRF, RCE lub supply chain attack w aplikacjach klientów wpływający na infrastrukturę platformy.
- Przejęcie konta użytkownika lub administratora przez słabe sesje, brak MFA albo phishing.
- Błędna obsługa webhooków Stripe prowadząca do fałszywych aktywacji subskrypcji.
- Wyciek sekretów przez logi, zmienne środowiskowe, obrazy kontenerów lub błędne uprawnienia.
- Nadużycia domen własnych, w tym domain takeover, błędna weryfikacja właścicielstwa i hostowanie treści phishingowych.
- Niepełny audit trail utrudniający wykrycie i analizę incydentu.
- Brak odporności na ataki wolumetryczne, brute force, credential stuffing i abuse automatyzacji deploymentów.
- Niebezpieczne domyślne konfiguracje Kubernetes, ingressu, obrazów bazowych i bibliotek.
- Nadmierne uprawnienia serwisów control plane do Kubernetes API, Stripe, DNS lub secret store.

## 8. Decyzje architektoniczne

- Przyjmujemy rozdział na control plane i data plane. Control plane zarządza stanem i decyzjami, data plane wykonuje workloady klientów.
- Kubernetes jest podstawowym runtime dla aplikacji klientów.
- Każdy projekt lub środowisko projektu działa w osobnym namespace Kubernetes.
- Tenant workloady są traktowane jako niezaufane i nie otrzymują dostępu do API control plane poza jawnie wystawionymi endpointami.
- Izolacja MVP opiera się na namespace, Kubernetes RBAC, NetworkPolicy, ResourceQuota, LimitRange, Pod Security Admission, security context i oddzielnych service accountach.
- Dla klientów lub planów wyższego ryzyka przewidujemy docelowo izolację przez dedykowane node poole albo dedykowane klastry.
- Źródłem prawdy dla tenantów, organizacji, projektów, subskrypcji i uprawnień jest relacyjna baza danych control plane.
- Operacje provisioningowe są asynchroniczne, idempotentne i oparte na zdarzeniach lub kolejce.
- Każda operacja zmieniająca stan tenantów, billing, domen, deploymentów lub uprawnień musi emitować audit event.
- Stripe jest systemem źródłowym dla płatności i faktur, ale platforma utrzymuje własny zmaterializowany billing state potrzebny do autoryzacji limitów.
- Webhooki Stripe muszą być weryfikowane podpisem, idempotentne i odporne na opóźnienia oraz powtórzenia.
- Certyfikaty TLS są automatyzowane przez cert-manager i ACME.
- Własność domeny jest weryfikowana przed aktywacją routingu produkcyjnego.
- Publiczne API jest projektowane jako explicit tenant context: każda operacja musi jednoznacznie wskazywać organizację i projekt albo wynikać z bezpiecznego kontekstu.
- Autoryzacja jest centralizowana w warstwie serwisowej, a nie rozproszona wyłącznie po UI.
- Logi, metryki i audit trail są logicznie separowane per tenant i filtrowane na granicy dostępu.
- Sekrety przechowujemy w dedykowanym secret store/KMS, a nie w bazie aplikacyjnej jako plain text.
- Domyślnie preferujemy deny-by-default dla sieci, uprawnień i operacji administracyjnych.
- Architektura musi umożliwiać późniejsze zaostrzenie wymagań do ASVS Level 3 bez przepisywania modelu tożsamości, audytu i izolacji.

## 9. Rzeczy, których celowo nie robimy w pierwszej wersji

- Nie budujemy od razu pełnego PaaS z dowolnym build systemem, marketplace i zaawansowanymi pipeline'ami CI/CD.
- Nie oferujemy dedykowanego klastra dla każdego klienta w standardowym planie MVP.
- Nie wdrażamy własnego systemu płatności ani fakturowania poza integracją ze Stripe.
- Nie implementujemy niestandardowych ról RBAC w MVP, poza ustalonym zestawem ról podstawowych.
- Nie obsługujemy SSO/SAML/OIDC dla organizacji w pierwszej wersji.
- Nie gwarantujemy jeszcze pełnej zgodności z ASVS Level 3.
- Nie budujemy własnego Certificate Authority.
- Nie automatyzujemy DNS dla wszystkich zewnętrznych providerów domen; w MVP klient może konfigurować rekordy ręcznie.
- Nie udostępniamy prywatnego networkingu do zasobów klientów.
- Nie oferujemy gwarantowanej izolacji sprzętowej dla każdego tenanta.
- Nie wdrażamy zaawansowanego WAF per tenant jako funkcji self-service.
- Nie zapewniamy od razu multi-region active-active.
- Nie przechowujemy logów aplikacyjnych bez ograniczeń czasowych i kosztowych.
- Nie pozwalamy workloadom klientów na uprzywilejowane kontenery, hostPath, hostNetwork ani dostęp do socketu kontenera.
- Nie udostępniamy bezpośredniego dostępu klientów do Kubernetes API.

## 10. Kryteria gotowości produkcyjnej

### Architektura i funkcjonalność

- Użytkownik może założyć konto, utworzyć organizację, projekt, wdrożyć aplikację i podpiąć domenę.
- Subskrypcja Stripe poprawnie aktywuje, odnawia, blokuje i odblokowuje dostęp zgodnie ze statusem płatności.
- Deploymenty klientów są tworzone, aktualizowane, zawieszane i usuwane przez kontrolowany orchestrator.
- Domena własna nie kieruje ruchu do workloadu, dopóki własność domeny i TLS nie są poprawnie skonfigurowane.
- Limity zasobów są egzekwowane per projekt lub tenant.
- Usunięcie projektu usuwa albo bezpiecznie wygasza powiązane zasoby runtime, domeny, certyfikaty i sekrety.

### Bezpieczeństwo

- Wykonano threat modeling dla kluczowych przepływów: auth, RBAC, deployment, domain verification, Stripe webhook, Kubernetes provisioning i audit logging.
- Wymagania OWASP ASVS Level 2 są zmapowane na kontrolki, testy lub świadome wyjątki.
- MFA jest wymagane dla kont administracyjnych.
- Każdy endpoint API ma testy autoryzacji obejmujące dostęp między tenantami.
- Sekrety nie są logowane, commitowane ani przechowywane jako plain text.
- Webhooki Stripe są weryfikowane podpisem i obsługiwane idempotentnie.
- Workloady klientów działają bez uprawnień privileged, bez root tam, gdzie to możliwe, z ograniczonym filesystemem i minimalnym zestawem capabilities.
- NetworkPolicy ogranicza ruch między tenantami i do komponentów control plane.
- Obrazy platformy i zależności są skanowane pod kątem podatności.
- Istnieje proces rotacji kluczy, sekretów i tokenów dostępowych.
- Audit log obejmuje logowania, zmiany ról, billing, domeny, deploymenty, operacje administracyjne i zdarzenia bezpieczeństwa.

### Operacje

- Monitoring obejmuje control plane, Kubernetes, ingress, certyfikaty, kolejki, bazę danych, metering i integrację Stripe.
- Alerty istnieją dla awarii krytycznych, błędów certyfikatów, braku odnowienia TLS, błędów webhooków, przeciążenia zasobów i naruszeń limitów.
- Istnieją runbooki dla awarii deploymentów, problemów z domeną, incydentu bezpieczeństwa, błędu billingowego i awarii bazy danych.
- Backupy bazy danych i konfiguracji są automatyczne, monitorowane i przetestowane przez restore.
- System ma zdefiniowane SLO dla panelu, API, routingu aplikacji klientów i operacji deploymentu.
- Logi i metryki mają polityki retencji, limity kosztowe i kontrolę dostępu per tenant.
- Istnieje środowisko staging możliwie zbliżone do produkcji.
- Migracje bazy danych są wersjonowane, odwracalne tam, gdzie realistyczne, i testowane przed produkcją.

### Jakość i release

- Kluczowe przepływy mają testy automatyczne: auth, RBAC, organizacje, projekty, billing, webhooki, domeny i deployment orchestration.
- Testy end-to-end obejmują minimum ścieżkę: rejestracja -> organizacja -> subskrypcja -> projekt -> domena -> deployment -> logi -> usunięcie.
- Przeprowadzono testy obciążeniowe dla API, ingressu i podstawowego scenariusza deploymentu.
- Przeprowadzono security review i naprawiono krytyczne oraz wysokie podatności.
- CI/CD wymusza testy, linting, skan zależności i skan obrazów.
- Release może być wycofany lub zatrzymany bez ręcznego modyfikowania produkcyjnej bazy danych.
- Dokumentacja operacyjna i architektoniczna jest dostępna dla zespołu utrzymującego platformę.
