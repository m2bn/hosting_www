# Threat model platformy SaaS do hostingu stron i aplikacji

## 1. Cel dokumentu

Ten dokument opisuje główne zagrożenia dla multi-tenant platformy SaaS do hostingu stron i aplikacji klientów. Model bazuje na architekturze opisanej w `docs/architecture/vision.md` i koncentruje się na wymaganiach produkcyjnego MVP z możliwością późniejszego dojścia do OWASP ASVS Level 3.

Zakładamy, że niezaufane są:

- ruch publiczny z Internetu;
- użytkownicy końcowi i ich przeglądarki;
- aplikacje klientów uruchamiane w runtime;
- uploadowane pliki i artefakty;
- obrazy kontenerowe, zależności i kod klientów;
- webhooki oraz requesty z systemów zewnętrznych do momentu ich kryptograficznej weryfikacji;
- dane wejściowe przekazywane do API, panelu, buildera, domen, logów i meteringu.

## 2. Zakres modelu

Model obejmuje:

- użytkowników, organizacje, projekty i role;
- Public API, Web App i Admin Console;
- sesje użytkowników, API keys i dostęp operatorów platformy;
- billing przez Stripe i webhooki Stripe;
- domeny własne i automatyczne certyfikaty SSL;
- upload plików oraz artefakty deploymentów;
- budowanie obrazów kontenerowych i supply chain;
- runtime aplikacji klientów w Kubernetes;
- izolację tenantów oraz izolację projektów klientów;
- logi, audit logi, metryki, dane osobowe i backupy.

Poza zakresem tego dokumentu są szczegółowe diagramy przepływu danych, konkretna implementacja providerów chmurowych oraz finalna macierz ASVS. Te artefakty powinny powstać jako kolejne dokumenty.

## 3. Metoda STRIDE

Kategorie STRIDE używane w dokumencie:

- Spoofing: podszycie się pod użytkownika, usługę, domenę, workload lub system zewnętrzny.
- Tampering: nieautoryzowana modyfikacja danych, konfiguracji, artefaktów, obrazów lub zdarzeń.
- Repudiation: możliwość wyparcia się wykonanej operacji z powodu braku wiarygodnego audytu.
- Information Disclosure: ujawnienie danych tenantów, sekretów, danych osobowych, logów lub konfiguracji.
- Denial of Service: niedostępność systemu, wyczerpanie zasobów lub kosztowy abuse.
- Elevation of Privilege: uzyskanie wyższych uprawnień w aplikacji, control plane, runtime albo infrastrukturze.

## 4. Skala ryzyka

Prawdopodobieństwo:

- Niskie: wymaga wielu warunków, uprzywilejowanego dostępu lub zaawansowanych umiejętności.
- Średnie: realistyczne w typowym środowisku SaaS, ale wymaga błędu konfiguracji, luki lub nietrywialnej sekwencji działań.
- Wysokie: typowy wektor dla aplikacji internetowych, łatwy do automatyzacji albo często spotykany przy tej klasie systemu.

Wpływ:

- Niski: ograniczony wpływ na pojedynczą funkcję bez naruszenia poufności lub integralności ważnych danych.
- Średni: naruszenie pojedynczego projektu, ograniczony wyciek danych, lokalna niedostępność albo koszt operacyjny.
- Wysoki: naruszenie wielu tenantów, danych osobowych, billing state, runtime, sekretów, ciągłości usługi lub zaufania do platformy.

## 5. Główne aktywa

- tożsamości użytkowników, operatorów i usług;
- organizacje, członkostwa, role i uprawnienia;
- projekty, konfiguracje deploymentów, domeny i certyfikaty;
- subskrypcje, faktury, status płatności i billing state;
- API keys, tokeny sesji, tokeny operatorów, sekrety integracji;
- obrazy kontenerowe, artefakty buildów i uploadowane pliki;
- workloady klientów, namespace Kubernetes, service accounty i polityki runtime;
- logi aplikacyjne, audit logi, metryki, dane meteringowe i backupy;
- dane osobowe użytkowników i operatorów.

## 6. Granice zaufania

Kluczowe granice zaufania:

- przeglądarka użytkownika -> Web App/Public API;
- Public API -> usługi control plane;
- control plane -> baza danych, kolejki, cache, secret store i KMS;
- control plane -> Kubernetes API;
- Internet -> Ingress/Gateway -> workload klienta;
- workload klienta -> inne workloady, metadata endpoints, Internet i usługi platformy;
- Stripe -> endpoint webhooków billingowych;
- DNS/ACME -> usługi domen i certyfikatów;
- operator platformy -> Admin Console i narzędzia operacyjne;
- logi, metryki i backupy -> użytkownicy, operatorzy i procesy eksportu.

## 7. Zagrożenia

### T01: IDOR i broken access control między tenantami

- STRIDE: Information Disclosure, Tampering, Elevation of Privilege
- Opis: Użytkownik jednej organizacji uzyskuje dostęp do zasobów innej organizacji przez manipulację identyfikatorami organizacji, projektu, deploymentu, domeny, logów lub billing state.
- Wektor ataku: Zmiana `organization_id`, `project_id`, `domain_id` lub `deployment_id` w URL, body requestu, GraphQL variables, API key scope albo filtrach listowania.
- Wpływ: Wysoki. Możliwy wyciek danych klienta, modyfikacja deploymentu, przejęcie domeny, odczyt logów, zmiana ról lub naruszenie billing state.
- Prawdopodobieństwo: Wysokie.
- Mitigacje: Centralny mechanizm autoryzacji; jawny tenant context dla każdej operacji; sprawdzanie członkostwa i roli po stronie serwera; brak zaufania do tenant context z UI; testy negatywne dla każdego endpointu; zapytania bazodanowe zawsze filtrowane tenantem; unikanie globalnych sekwencyjnych identyfikatorów w publicznym API; audit event dla operacji cross-resource.
- Testy weryfikujące: Testy integracyjne próbujące odczytu, modyfikacji i usunięcia zasobów innego tenanta; fuzzing identyfikatorów w API; testy regresyjne RBAC dla każdej roli; testy listowania zasobów bez filtra tenantowego; skan DAST pod kątem IDOR.

### T02: Błędna izolacja projektów klientów w Kubernetes

- STRIDE: Information Disclosure, Tampering, Denial of Service, Elevation of Privilege
- Opis: Workload jednego projektu wpływa na workload innego projektu albo uzyskuje dostęp do jego sieci, sekretów, wolumenów, logów lub service accountów.
- Wektor ataku: Brak lub błędna NetworkPolicy, współdzielone service accounty, nadmierne RBAC, brak ResourceQuota, błędne etykiety namespace, wspólne persistent volume albo niepoprawny ingress routing.
- Wpływ: Wysoki. Możliwa kompromitacja wielu projektów, utrata poufności danych, modyfikacja runtime i niedostępność usługi.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Namespace per projekt lub środowisko; deny-by-default NetworkPolicy; oddzielne service accounty; minimalne RBAC; ResourceQuota i LimitRange; Pod Security Admission na poziomie restricted; zakaz privileged, hostPath, hostNetwork i hostPID; automatyczne testy polityk Kubernetes; admission control dla zasobów tworzonych przez orchestrator.
- Testy weryfikujące: Testy e2e próbujące komunikacji między namespace; próba odczytu sekretów innego projektu; próba uruchomienia privileged pod; test przekroczenia quota; test poprawności etykiet i właścicieli zasobów; okresowy audit manifestów przez policy-as-code.

### T03: Ucieczka z kontenera lub eskalacja uprawnień workloadu klienta

- STRIDE: Elevation of Privilege, Tampering, Information Disclosure
- Opis: Aplikacja klienta lub złośliwy obraz kontenerowy wykorzystuje podatność runtime, jądra, CNI, CSI albo błędną konfigurację poda, aby uzyskać dostęp do node'a lub klastra.
- Wektor ataku: Privileged container, dodatkowe Linux capabilities, podatny runtime kontenerowy, montowanie hostPath, dostęp do socketu kontenera, uruchamianie jako root, podatny kernel albo źle skonfigurowany seccomp/AppArmor.
- Wpływ: Wysoki. Możliwy dostęp do danych innych tenantów, sekretów, kubelet API, node filesystem i control plane.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Restricted Pod Security; seccomp/AppArmor; rootless lub non-root containers tam, gdzie możliwe; read-only root filesystem dla workloadów wspierających ten tryb; zakaz hostPath i socketów; aktualizacje node'ów; oddzielne node poole dla workloadów niezaufanych; runtime sandboxing dla wyższych planów lub ryzykownych workloadów; skanowanie obrazów; monitoring anomalii.
- Testy weryfikujące: Testy admission policy blokujące niebezpieczne pola; próby deploymentu podów privileged i hostPath; skan konfiguracji klastra CIS Kubernetes Benchmark; okresowe testy izolacji runtime; kontrolowany test dostępu do metadata/kubelet z poda.

### T04: SSRF z aplikacji klienta lub funkcji platformy

- STRIDE: Information Disclosure, Tampering, Elevation of Privilege
- Opis: Atakujący wymusza żądania HTTP z infrastruktury platformy lub workloadu do wewnętrznych adresów, metadata service, paneli administracyjnych, usług control plane albo endpointów chmurowych.
- Wektor ataku: URL podany w konfiguracji deploymentu, webhooku klienta, importu zasobów, pobierania artefaktów, preview, screenshotów, walidacji domeny albo aplikacji klienta.
- Wpływ: Wysoki. Możliwy wyciek tokenów metadata, skanowanie sieci wewnętrznej, dostęp do usług administracyjnych lub pivot do control plane.
- Prawdopodobieństwo: Wysokie.
- Mitigacje: Walidacja i normalizacja URL; blokada adresów prywatnych, loopback, link-local i metadata endpoints; DNS rebinding protection; egress NetworkPolicy; brak dostępu tenant workloadów do control plane; proxy egress z allowlistą dla funkcji platformowych; timeouts i limity redirectów; oddzielne środowisko dla pobierania niezaufanych zasobów.
- Testy weryfikujące: Testy URL z `127.0.0.1`, `localhost`, IPv6 loopback, link-local, RFC1918, metadata IP i DNS rebinding; testy redirectów do adresów prywatnych; testy egress policy z poda; DAST dla pól URL.

### T05: RCE w control plane przez upload, parsery lub builder

- STRIDE: Tampering, Information Disclosure, Elevation of Privilege, Denial of Service
- Opis: Złośliwy plik, archiwum, manifest, Dockerfile lub artefakt wykorzystuje podatność parsera, narzędzia build albo procesu walidacji i wykonuje kod w kontekście usługi platformy.
- Wektor ataku: Upload archiwum z path traversal, zip bomb, złośliwy plik konfiguracyjny, podatny parser YAML/JSON, złośliwy Dockerfile, build hooks albo podatny skaner obrazu.
- Wpływ: Wysoki. Możliwe przejęcie usługi, sekretów, kolejki buildów, registry albo bazy danych.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Upload i build w izolowanym sandboxie bez sekretów produkcyjnych; limity rozmiaru, czasu i liczby plików; bezpieczna ekstrakcja archiwów; skan antymalware tam, gdzie uzasadnione; parsowanie bez wykonywania kodu; oddzielne konta usługowe dla buildera; brak dostępu buildera do control plane poza wąskim API; aktualizacje narzędzi build i skanerów.
- Testy weryfikujące: Testy path traversal w archiwach; testy zip bomb i limitów rozmiaru; testy złośliwych symlinków; testy Dockerfile próbującego odczytu sekretów; SAST/DAST parserów; testy izolacji środowiska build.

### T06: Supply-chain attack w zależnościach, obrazach i pipeline

- STRIDE: Tampering, Information Disclosure, Elevation of Privilege
- Opis: Złośliwa lub przejęta zależność, obraz bazowy, akcja CI, plugin buildera albo pakiet klienta zostaje wykonany w procesie build lub runtime.
- Wektor ataku: Dependency confusion, typosquatting, przejęte konto maintainerów, niezapinowane wersje obrazów, złośliwy base image, niezweryfikowane artefakty, niekontrolowane skrypty postinstall.
- Wpływ: Wysoki. Możliwe przejęcie buildów, wyciek sekretów, backdoor w obrazach klientów lub platformy i eskalacja do infrastruktury.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Pinning wersji i digestów obrazów; SBOM; skan zależności i obrazów; podpisywanie artefaktów; weryfikacja provenance; oddzielenie build secrets; minimalne uprawnienia CI; prywatne registry z politykami; allowlista builderów i base image dla MVP; blokowanie znanych podatności krytycznych.
- Testy weryfikujące: Skan dependency confusion; weryfikacja digestów w manifestach; test blokady obrazu bez podpisu; generowanie i kontrola SBOM; test polityk CI bez dostępu do sekretów w pull requestach; próbny build z podatnym obrazem bazowym.

### T07: Podszycie się pod Stripe webhook lub replay zdarzeń

- STRIDE: Spoofing, Tampering, Repudiation
- Opis: Atakujący wysyła fałszywe lub powtórzone zdarzenie Stripe, aby aktywować subskrypcję, zmienić plan, odblokować organizację albo zaburzyć billing state.
- Wektor ataku: Request HTTP do endpointu webhooków bez poprawnego podpisu, replay starego eventu, manipulacja payloadem, wysłanie eventów poza kolejnością.
- Wpływ: Wysoki. Możliwe straty finansowe, nieuprawniony dostęp do usługi, błędne blokady klientów i niespójność rozliczeń.
- Prawdopodobieństwo: Wysokie, jeśli endpoint jest publiczny i źle chroniony; niskie po poprawnej implementacji podpisów.
- Mitigacje: Weryfikacja `Stripe-Signature`; ograniczone okno czasowe; idempotencja po `event_id`; pobieranie krytycznych danych z Stripe API zamiast ufania payloadowi; obsługa out-of-order events; kolejka i transakcyjny update billing state; audit billing events.
- Testy weryfikujące: Test webhooka bez podpisu; test z błędnym podpisem; test replay tego samego eventu; test zdarzeń poza kolejnością; test payload tampering; test awarii pośredniej i ponownego przetworzenia.

### T08: Przejęcie lub błędna weryfikacja domeny własnej

- STRIDE: Spoofing, Tampering, Information Disclosure
- Opis: Atakujący podpina domenę, której nie kontroluje, albo przejmuje nieużywany routing domeny innego klienta.
- Wektor ataku: Brak weryfikacji DNS TXT/CNAME, race condition przy przypisywaniu domen, stale pozostawiony rekord DNS, ponowne użycie domeny po usunięciu projektu, wildcard routing bez jednoznacznego właściciela.
- Wpływ: Wysoki. Możliwe domain takeover, phishing, przechwycenie ruchu, reputacyjne szkody i naruszenie danych.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Weryfikacja własności domeny przed routingiem; unikalny token w DNS; blokada duplikatów domen globalnie; okresowa rewalidacja; bezpieczny lifecycle usuwania domen; opóźnione zwalnianie domeny; audit operacji domenowych; jednoznaczne mapowanie host -> project.
- Testy weryfikujące: Test aktywacji domeny bez rekordu weryfikacyjnego; test próby dodania tej samej domeny w dwóch organizacjach; test usunięcia i ponownego dodania domeny; test wildcard collision; test rewalidacji po zmianie DNS.

### T09: Błędne wystawienie, odnowienie lub ujawnienie certyfikatu SSL

- STRIDE: Spoofing, Information Disclosure, Denial of Service
- Opis: Platforma wystawia certyfikat dla niezweryfikowanej domeny, nie odnawia certyfikatu, ujawnia klucz prywatny albo miesza certyfikaty między tenantami.
- Wektor ataku: Błędna integracja cert-manager/ACME, złe mapowanie secretów TLS, brak owner references, współdzielone secret names, limity ACME, błędna obsługa wildcard certs.
- Wpływ: Wysoki. Możliwe podszycie, przerwa w działaniu domen klienta, wyciek kluczy prywatnych i utrata zaufania.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Certyfikat wyłącznie po weryfikacji domeny; secret TLS per domena/projekt; separacja namespace; monitoring expiry; alerty odnowień; brak ekspozycji kluczy prywatnych w UI/logach; rotacja po incydencie; limity i backoff dla ACME.
- Testy weryfikujące: Test próby certyfikatu bez zweryfikowanej domeny; test kolizji nazw secretów; test odnowienia certyfikatu na staging ACME; test alertu przed expiry; test braku kluczy prywatnych w logach i API.

### T10: Przejęcie sesji użytkownika

- STRIDE: Spoofing, Elevation of Privilege, Information Disclosure
- Opis: Atakujący uzyskuje dostęp do aktywnej sesji użytkownika przez kradzież cookie, XSS, fixation, słabą rotację tokenów albo brak ochrony przed credential stuffing.
- Wektor ataku: XSS w panelu, token w localStorage, brak `HttpOnly`, `Secure` lub `SameSite`, brak rotacji po logowaniu, brak detekcji anomalii, phishing.
- Wpływ: Wysoki. Możliwe przejęcie organizacji, projektów, domen, deploymentów i billing actions zgodnie z rolą ofiary.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Cookies `HttpOnly`, `Secure`, `SameSite`; rotacja session id po logowaniu i zmianie uprawnień; CSRF protection; CSP; krótkie TTL i refresh flow; MFA dla administratorów i opcjonalnie organizacji; rate limiting logowania; wykrywanie credential stuffing; możliwość unieważnienia sesji.
- Testy weryfikujące: Test flag cookie; test session fixation; test CSRF; test rotacji sesji po logowaniu i zmianie hasła; test rate limit logowania; test XSS w polach panelu; test wylogowania ze wszystkich urządzeń.

### T11: Nadużycie lub wyciek API keys

- STRIDE: Spoofing, Tampering, Information Disclosure, Elevation of Privilege
- Opis: API key klienta lub operatora zostaje skradziony, ma zbyt szerokie uprawnienia albo nie jest możliwy do szybkiej rotacji.
- Wektor ataku: Klucz zapisany w repozytorium, logach, obrazie kontenerowym, CI variables, przeglądarce albo przekazany w URL; brak scope; brak expiry; brak rate limit.
- Wpływ: Wysoki. Możliwa automatyczna modyfikacja projektów, deploymentów, domen, logów i danych organizacji.
- Prawdopodobieństwo: Średnie.
- Mitigacje: API keys z jawnymi scope i tenant binding; wyświetlanie sekretu tylko raz; hashowanie kluczy w bazie; prefiksy identyfikacyjne bez ujawniania sekretu; expiry i rotacja; rate limiting; audit użycia; blokada kluczy w URL; secret scanning w logach.
- Testy weryfikujące: Test dostępu poza scope; test odwołanego klucza; test expiry; test, że klucz nie jest przechowywany plain text; test maskowania w logach; test rate limiting API keys.

### T12: Kompromitacja panelu admina

- STRIDE: Spoofing, Tampering, Repudiation, Information Disclosure, Elevation of Privilege
- Opis: Atakujący uzyskuje dostęp do Admin Console lub wykonuje operacje administracyjne bez właściwego poziomu autoryzacji i audytu.
- Wektor ataku: Brak MFA, phishing operatora, XSS/CSRF w panelu, podatność w endpointach admina, zbyt szerokie role, dostęp z niekontrolowanych sieci.
- Wpływ: Wysoki. Możliwa pełna kompromitacja tenantów, billing state, domen, sekretów, deploymentów i danych osobowych.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Wymuszone MFA; osobne role administracyjne; just-in-time access dla operacji wysokiego ryzyka; allowlista sieci lub device posture tam, gdzie możliwe; step-up auth; pełny audit log; zasada dwóch osób dla operacji destrukcyjnych docelowo; brak bezpośredniego dostępu do sekretów.
- Testy weryfikujące: Test blokady admina bez MFA; test CSRF dla akcji admina; test ról operatorów; test step-up dla blokady organizacji/usunięcia projektu; test kompletności audit logu; test sesji admina po zmianie roli.

### T13: Nadużycie dostępu operatorów platformy

- STRIDE: Repudiation, Information Disclosure, Tampering, Elevation of Privilege
- Opis: Operator platformy nadużywa legalnych uprawnień albo konto operatora zostaje przejęte i użyte do działań na tenantach.
- Wektor ataku: Stałe szerokie uprawnienia, brak just-in-time access, brak rozdziału obowiązków, brak alertów na operacje wrażliwe, niepełny audit.
- Wpływ: Wysoki. Możliwy nieautoryzowany dostęp do danych klientów, modyfikacja deploymentów i ukrycie śladów.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Least privilege; osobne konta operatorów; JIT/JEA dla dostępu produkcyjnego; pełny, append-only audit; alerty na dostęp do danych klienta; break-glass z rejestracją powodu; okresowe review uprawnień; separacja obowiązków.
- Testy weryfikujące: Test wymogu podania powodu dostępu; test audytu odczytu danych tenantów; test wygaśnięcia JIT; test braku możliwości modyfikacji audit logu przez operatora; review uprawnień w ramach kontroli okresowej.

### T14: Ujawnienie logów, danych osobowych lub sekretów

- STRIDE: Information Disclosure, Repudiation
- Opis: Logi aplikacyjne, systemowe, audit trail lub metryki zawierają dane osobowe, tokeny, klucze API, sekrety, nagłówki autoryzacyjne lub dane innych tenantów.
- Wektor ataku: Logowanie pełnych requestów, stack trace, exception z sekretami, brak maskowania, wspólny indeks logów, błędne filtry tenantowe, eksport logów do niewłaściwej organizacji.
- Wpływ: Wysoki. Możliwy wyciek danych osobowych, sekretów i informacji operacyjnych ułatwiających dalszy atak.
- Prawdopodobieństwo: Wysokie.
- Mitigacje: Polityka klasyfikacji i maskowania danych; zakaz logowania sekretów i pełnych payloadów; tenant-aware log access; oddzielne indeksy lub twarde filtry tenantowe; retencja logów; redakcja nagłówków; testy secret scanning; minimalizacja danych osobowych.
- Testy weryfikujące: Test logowania requestów z tokenami; secret scanning logów; test dostępu do logów innego projektu; test eksportu logów; test retencji; test maskowania danych osobowych i nagłówków.

### T15: Manipulacja lub usunięcie audit logów

- STRIDE: Repudiation, Tampering
- Opis: Atakujący lub operator usuwa albo modyfikuje audit log, aby ukryć nieautoryzowane operacje.
- Wektor ataku: Zapis audit logów do zwykłej tabeli bez ograniczeń, brak podpisów lub hash chain, nadmierne uprawnienia operatorów, brak kopii do niezależnego store.
- Wpływ: Wysoki. Utrata możliwości wykrycia, analizy i udowodnienia incydentu.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Append-only audit store; ograniczenie uprawnień do zapisu; brak operacji update/delete przez aplikację; opcjonalny hash chain lub podpisy; replikacja do niezależnego systemu; alerty na przerwy w emisji audit eventów; korelacja z logami infrastruktury.
- Testy weryfikujące: Test braku endpointu modyfikacji audit logu; test uprawnień DB; test ciągłości sekwencji eventów; test alertu na brak audit events; próba modyfikacji rekordu przez konto aplikacyjne.

### T16: Ujawnienie lub utrata backupów

- STRIDE: Information Disclosure, Tampering, Denial of Service
- Opis: Backupy bazy danych, obiektów, logów lub konfiguracji są niezaszyfrowane, dostępne zbyt szeroko, niekompletne albo niemożliwe do odtworzenia.
- Wektor ataku: Publiczny bucket, wyciek klucza backupowego, brak szyfrowania, brak separacji tenantów, nadmierne retencje, brak testów restore, backup sekretów bez KMS.
- Wpływ: Wysoki. Możliwy masowy wyciek danych tenantów i danych osobowych albo utrata ciągłości usługi po awarii.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Szyfrowanie backupów KMS; least privilege dla backup/restore; bucket policy deny public; immutable backups; testy restore; retencja zgodna z polityką danych; osobne uprawnienia do odtwarzania produkcji; audit dostępu do backupów.
- Testy weryfikujące: Test public access block; test restore na staging; test uprawnień do backupów; test szyfrowania; test usunięcia backupu przez konto bez uprawnień; test kompletności backupu danych krytycznych.

### T17: Upload plików jako kanał ataku na użytkowników lub infrastrukturę

- STRIDE: Tampering, Information Disclosure, Denial of Service, Elevation of Privilege
- Opis: Uploadowane pliki są używane do przechowania malware, wykonania XSS, path traversal, przeciążenia storage albo dostarczenia treści aktywnej innym użytkownikom.
- Wektor ataku: Pliki HTML/SVG z JavaScriptem, polyglot files, bardzo duże pliki, dużo małych plików, złośliwe nazwy plików, content-type spoofing, publiczny direct serving z domeny panelu.
- Wpływ: Średni do wysokiego. Możliwy XSS, malware hosting, wzrost kosztów, niedostępność i kompromitacja użytkowników.
- Prawdopodobieństwo: Wysokie.
- Mitigacje: Limity rozmiaru i liczby plików; przechowywanie poza domeną panelu; bezpieczny `Content-Disposition`; walidacja rozszerzeń i MIME; losowe nazwy obiektów; brak wykonywania uploadowanych plików; skanowanie malware dla wybranych typów; quota per projekt; lifecycle cleanup.
- Testy weryfikujące: Test uploadu HTML/SVG z JS; test content-type spoofing; test limitów rozmiaru; test path traversal w nazwie pliku; test serving headers; test quota storage; test malware fixture w środowisku testowym.

### T18: Niebezpieczne budowanie obrazów kontenerowych klientów

- STRIDE: Tampering, Information Disclosure, Denial of Service, Elevation of Privilege
- Opis: Proces build wykonuje niezaufany kod klienta i może zostać użyty do kradzieży sekretów, ataku na sieć wewnętrzną, przejęcia cache albo wyczerpania zasobów.
- Wektor ataku: Dockerfile wykonujący skrypty exfiltrujące dane, build context z symlinkami, złośliwe dependency hooks, cache poisoning, build trwający bez limitu, dostęp do sieci wewnętrznej.
- Wpływ: Wysoki. Możliwa kompromitacja sekretów build, registry, cache i infrastruktury.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Izolowany builder per job; brak sekretów platformy w build context; krótkotrwałe tokeny registry; limity CPU/RAM/czasu; kontrolowany egress; czyszczenie cache per tenant lub bezpieczne namespacing; rootless build tam, gdzie możliwe; skan obrazu przed publikacją; jawna polityka dozwolonych funkcji build.
- Testy weryfikujące: Test Dockerfile próbującego odczytu env i metadata; test symlink traversal w build context; test timeout build; test cache isolation między tenantami; test egress do prywatnych adresów; test publikacji obrazu z krytyczną podatnością.

### T19: Denial of Service i noisy neighbor w runtime

- STRIDE: Denial of Service
- Opis: Jeden tenant wyczerpuje CPU, RAM, storage, transfer, limity ingressu, kolejki deploymentów albo log ingestion, pogarszając działanie innych tenantów lub control plane.
- Wektor ataku: Pętla CPU, memory leak, duży ruch HTTP, nadmierna liczba deploymentów, generowanie ogromnych logów, duże uploady, nadużycie webhooków i API.
- Wpływ: Średni do wysokiego. Możliwa niedostępność projektów innych klientów, wzrost kosztów i degradacja control plane.
- Prawdopodobieństwo: Wysokie.
- Mitigacje: ResourceQuota, LimitRange, HPA z limitami, rate limiting API, limity deploymentów, quota logów i metryk, backpressure w kolejkach, per-tenant budgets, circuit breakers, oddzielenie control plane od data plane, alerting kosztowy.
- Testy weryfikujące: Test przekroczenia CPU/RAM quota; test burst API; test log flood; test kolejki deploymentów; test limitów uploadu; test izolacji control plane podczas przeciążenia tenant workload.

### T20: Manipulacja meteringiem i billing state

- STRIDE: Tampering, Repudiation, Information Disclosure
- Opis: Tenant, błąd systemu lub atakujący manipuluje danymi zużycia zasobów albo billing state, aby uniknąć opłat, zablokować innego klienta albo uzyskać wyższy plan.
- Wektor ataku: Fałszywe metryki, race condition przy zmianie planu, brak idempotencji eventów billingowych, bezpośrednia modyfikacja billing state, błędne mapowanie Stripe customer -> organization.
- Wpływ: Średni do wysokiego. Straty finansowe, spory z klientami, nieuprawniony dostęp lub blokada usług.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Metering z zaufanych źródeł infrastruktury; podpisane lub kontrolowane zdarzenia wewnętrzne; idempotentne aktualizacje; transakcyjne mapowanie Stripe customer; reconciliation ze Stripe; audit zmian planu; separacja uprawnień billing admin.
- Testy weryfikujące: Test duplikatów eventów; test mapowania customer do organizacji; test zmiany planu równolegle; test reconciliation; test próby wysłania metryk z workloadu klienta; test audytu ręcznych korekt.

### T21: XSS w panelu użytkownika lub admina

- STRIDE: Spoofing, Information Disclosure, Elevation of Privilege
- Opis: Dane kontrolowane przez klienta są renderowane w panelu użytkownika lub admina bez poprawnego escaping/sanitizacji, umożliwiając wykonanie JavaScriptu.
- Wektor ataku: Nazwa organizacji, projektu, domeny, deploymentu, logi aplikacyjne, komunikaty błędów builda, metadane uploadu, dane faktury.
- Wpływ: Wysoki. Możliwa kradzież sesji, wykonywanie akcji w imieniu użytkownika, przejęcie panelu admina albo eksfiltracja danych.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Automatyczne escaping w UI; sanitizacja HTML, jeśli HTML jest konieczny; CSP; brak tokenów w localStorage; bezpieczne renderowanie logów jako tekst; separacja domen dla treści klientów; testy komponentów na payloady XSS.
- Testy weryfikujące: Test payloadów XSS w nazwach zasobów; test logów zawierających HTML/JS; test CSP; test braku inline script tam, gdzie możliwe; DAST panelu; test renderowania metadanych uploadów.

### T22: CSRF dla akcji opartych o sesje cookie

- STRIDE: Spoofing, Tampering
- Opis: Atakujący wymusza akcję w panelu użytkownika lub admina, jeśli sesja jest utrzymywana w cookies i endpoint nie wymaga ochrony CSRF.
- Wektor ataku: Złośliwa strona wykonująca POST/PUT/DELETE do API platformy z cookies ofiary.
- Wpływ: Średni do wysokiego. Możliwa zmiana konfiguracji, zaproszenie użytkownika, rotacja domeny, rozpoczęcie deploymentu albo akcja admina.
- Prawdopodobieństwo: Średnie.
- Mitigacje: SameSite cookies; token CSRF dla mutacji; sprawdzanie Origin/Referer; oddzielenie auth dla API keys od cookie sessions; step-up auth dla krytycznych akcji; brak mutacji przez GET.
- Testy weryfikujące: Test mutacji bez tokenu CSRF; test błędnego Origin; test GET niezmieniających stanu; test SameSite cookie; test akcji admina z cross-site form.

### T23: Błędne zarządzanie sekretami klientów i platformy

- STRIDE: Information Disclosure, Tampering, Elevation of Privilege
- Opis: Sekrety są przechowywane lub przekazywane w sposób umożliwiający odczyt przez niewłaściwego tenanta, operatora, build job, logi albo workload.
- Wektor ataku: Sekrety w plain text w bazie, logach lub env dump; współdzielony Kubernetes Secret; brak rotacji; zbyt szeroki dostęp secret operatora; sekrety w build context.
- Wpływ: Wysoki. Możliwe przejęcie integracji klientów, dostępu do providerów, registry, Stripe, DNS lub control plane.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Secret store/KMS; szyfrowanie envelope; oddzielne sekrety per projekt; minimalne RBAC do secretów; maskowanie w UI/logach; rotacja; brak sekretów platformy w tenant runtime; audyt odczytu sekretów; sealed/external secrets.
- Testy weryfikujące: Test braku sekretów plain text w DB; test dostępu service account do sekretów innego projektu; test maskowania w API i UI; test rotacji sekretu; secret scanning repozytorium, logów i obrazów.

### T24: Nieautoryzowany dostęp do danych przez cache lub kolejki

- STRIDE: Information Disclosure, Tampering
- Opis: Dane tenantów trafiają do cache, kolejki lub topicu bez właściwego namespacingu, TTL, autoryzacji lub czyszczenia.
- Wektor ataku: Wspólny klucz cache bez tenant prefix, reuse job id, odczyt wiadomości z kolejki przez niewłaściwy worker, brak szyfrowania payloadu, błędny retry z innym kontekstem.
- Wpływ: Średni do wysokiego. Możliwy wyciek danych, wykonanie operacji w złym projekcie lub niespójny stan.
- Prawdopodobieństwo: Średnie.
- Mitigacje: Tenant-aware cache keys; minimalny payload w kolejkach; podpisy lub integralność jobów; dedykowane kolejki dla klas operacji; TTL; autoryzacja w momencie wykonania joba; idempotency keys; dead letter queue z kontrolą dostępu.
- Testy weryfikujące: Test kolizji kluczy cache między tenantami; test wykonania joba z nieistniejącym lub zmienionym uprawnieniem; test retry po usunięciu projektu; test dostępu do DLQ; test TTL danych w cache.

## 8. Scenariusze szczególnie krytyczne

Najwyższy priorytet w MVP mają scenariusze:

- IDOR i broken access control między tenantami;
- izolacja workloadów klientów w Kubernetes;
- RCE/SSRF przez upload, builder lub funkcje pobierające URL;
- weryfikacja webhooków Stripe;
- przejęcie domeny własnej lub błędne wydanie certyfikatu;
- kompromitacja panelu admina albo konta operatora;
- wyciek sekretów, logów, danych osobowych lub backupów;
- supply-chain attack w buildach i obrazach.

Te obszary powinny mieć testy automatyczne oraz manualny security review przed pierwszym wdrożeniem produkcyjnym.

## 9. Minimalne wymagania testowe przed produkcją

- Testy autoryzacji cross-tenant dla każdego endpointu API.
- Testy RBAC dla ról owner, admin, developer, viewer i operatorów platformy.
- Testy izolacji namespace, NetworkPolicy, ResourceQuota i Pod Security Admission.
- Testy SSRF dla wszystkich pól przyjmujących URL.
- Testy uploadu plików dla limitów, path traversal, content-type spoofing, aktywnej treści i malware fixtures.
- Testy buildera dla izolacji sekretów, limitów czasu, limitów zasobów, egress i cache isolation.
- Testy webhooków Stripe dla podpisu, replay, idempotencji i out-of-order events.
- Testy domen własnych dla weryfikacji, kolizji, usuwania i rewalidacji.
- Testy certyfikatów SSL dla wydania, odnowienia, błędów ACME, expiry alert i izolacji secretów TLS.
- Testy sesji użytkownika dla cookie flags, CSRF, session fixation, rotacji i unieważniania.
- Testy API keys dla scope, expiry, odwołania, maskowania i rate limitingu.
- Testy panelu admina dla MFA, step-up auth, RBAC, audit logu i CSRF.
- Testy dostępu operatorów dla JIT, break-glass, rejestracji powodu i audytu.
- Secret scanning repozytorium, obrazów, logów i artefaktów.
- Test restore backupu oraz kontrola szyfrowania i uprawnień do backupów.
- SAST, DAST, dependency scanning, image scanning i policy-as-code dla Kubernetes.

## 10. Otwarte decyzje bezpieczeństwa

- Czy buildy klientów w MVP są wykonywane przez platformę, czy platforma przyjmuje wyłącznie gotowe obrazy z zaufanego registry.
- Czy izolacja wybranych tenantów wymaga osobnych node pooli już w MVP.
- Jaki poziom egress control jest wymagany dla tenant workloadów w pierwszej wersji.
- Czy API keys są dostępne w MVP, czy dopiero po ustabilizowaniu modelu scope i audytu.
- Jak długo przechowujemy logi aplikacyjne, audit logi, metryki i backupy dla poszczególnych planów.
- Czy Admin Console wymaga allowlisty sieci lub device posture od pierwszej wersji.
- Czy certyfikaty wildcard są dopuszczalne, czy MVP używa wyłącznie certyfikatów per domena.
- Jakie operacje operatorów wymagają zasady dwóch osób w wersji docelowej.
