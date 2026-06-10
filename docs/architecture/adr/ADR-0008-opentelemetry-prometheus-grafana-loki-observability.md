# ADR-0008: OpenTelemetry + Prometheus + Grafana + Loki jako observability

## Status

Accepted

## Kontekst

Platforma wymaga obserwowalności control plane, data plane, Kubernetes, ingressu, certyfikatów, webhooków, deploymentów, billing, meteringu i workloadów klientów. Potrzebujemy spójnych metryk, logów, trace'ów, dashboardów i alertów.

## Decyzja

Stosem observability jest OpenTelemetry dla instrumentacji i trace'ów, Prometheus dla metryk, Grafana dla dashboardów oraz Loki dla logów.

## Konsekwencje pozytywne

- OpenTelemetry jest neutralnym standardem instrumentacji.
- Prometheus jest naturalnie dopasowany do Kubernetes i metryk infrastrukturalnych.
- Grafana zapewnia dashboardy i wspólny interfejs analizy.
- Loki dobrze pasuje do logów etykietowanych tenantem, projektem, usługą i correlation id.
- Stos jest popularny, przenośny i dobrze wspierany przez narzędzia cloud-native.

## Konsekwencje negatywne

- Stos wymaga kontroli kardynalności etykiet, retencji i kosztów.
- Loki nie zastępuje pełnego systemu SIEM ani archiwum audytowego.
- Błędne etykiety tenantowe mogą prowadzić do wycieku logów między klientami.
- Konfiguracja alertów i dashboardów wymaga aktywnej opieki, inaczej szybko traci jakość.

## Alternatywy

- Datadog/New Relic: szybszy start i mniej operacji, ale większy koszt oraz vendor lock-in.
- ELK/OpenSearch: mocne wyszukiwanie logów, ale większy koszt i cięższa operacja.
- Cloud-native monitoring providera: mniej własnej infrastruktury, ale słabsza przenośność.
- Grafana Cloud: dobry wariant zarządzany dla tego samego stosu, do rozważenia operacyjnie.

## Wpływ na bezpieczeństwo

- Logi i metryki muszą być separowane tenant context i nie mogą zawierać sekretów.
- Dostęp do dashboardów, logów i trace'ów musi być kontrolowany przez RBAC.
- Audit log nie może polegać wyłącznie na Loki; wymaga osobnego append-only store.
- Etykiety nie mogą zawierać danych osobowych ani sekretów.
- Monitoring musi obejmować zdarzenia bezpieczeństwa: błędy auth, rate limit, cross-tenant denials, certyfikaty, webhooki Stripe i naruszenia polityk Kubernetes.
