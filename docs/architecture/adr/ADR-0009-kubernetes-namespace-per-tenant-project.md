# ADR-0009: Namespace per tenant/project w Kubernetes

## Status

Accepted

## Kontekst

Runtime aplikacji klientów musi izolować projekty pod względem zasobów, sieci, sekretów, logów, metryk i uprawnień. MVP nie zakłada dedykowanego klastra dla każdego klienta, ale musi zapewnić rozsądną izolację zgodną z baseline bezpieczeństwa.

## Decyzja

Każdy tenant/project, a w razie potrzeby każde środowisko projektu, otrzymuje osobny namespace Kubernetes.

## Konsekwencje pozytywne

- Namespace daje naturalną granicę dla zasobów Kubernetes, RBAC, quota i NetworkPolicy.
- Ułatwia mapowanie projektu z control plane na zasoby runtime.
- Pozwala jasno tagować logi, metryki, koszty i alerty.
- Ułatwia lifecycle projektu: tworzenie, zawieszenie i usuwanie zasobów.
- Jest dobrym krokiem pośrednim przed dedykowanymi node poolami lub klastrami dla wyższych planów.

## Konsekwencje negatywne

- Namespace nie zapewnia pełnej izolacji bezpieczeństwa na poziomie jądra, node'a ani control plane.
- Duża liczba namespace może zwiększyć złożoność operacyjną i koszt listowania/monitoringu.
- Błędne etykiety lub owner references mogą powodować trudności w cleanupie.
- Współdzielone komponenty klastra nadal mogą być punktem ryzyka między tenantami.

## Alternatywy

- Namespace per organization: mniej namespace, ale słabsza izolacja między projektami.
- Namespace per environment: mocniejsza separacja środowisk, ale więcej obiektów do zarządzania.
- Dedicated node pool per tenant: lepsza izolacja zasobów, ale większy koszt.
- Dedicated cluster per tenant: najmocniejsza izolacja, ale poza zakresem standardowego MVP.

## Wpływ na bezpieczeństwo

- Namespace musi być tworzony wyłącznie przez orchestrator i mieć standardowy zestaw polityk.
- Każdy namespace musi mieć ResourceQuota, LimitRange, NetworkPolicy deny-by-default i dedykowany service account.
- Tenant workloady nie mogą widzieć sekretów, service accountów ani usług innych namespace.
- Testy izolacji namespace są wymagane przed produkcją.
- Dla klientów wysokiego ryzyka należy przewidzieć migrację do dedykowanych node pooli lub klastrów.
