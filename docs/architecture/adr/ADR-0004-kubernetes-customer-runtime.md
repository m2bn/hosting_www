# ADR-0004: Kubernetes jako runtime aplikacji klientów

## Status

Accepted

## Kontekst

Platforma hostuje aplikacje klientów jako odseparowane workloady. Potrzebujemy standardowego środowiska uruchomieniowego, autoscalingu, izolacji zasobów, integracji z ingress, certyfikatami, logami, metrykami oraz politykami bezpieczeństwa.

## Decyzja

Aplikacje klientów uruchamiamy w Kubernetes.

## Konsekwencje pozytywne

- Kubernetes jest standardem dla uruchamiania kontenerów i ma szeroki ekosystem.
- Umożliwia deklaratywne zarządzanie deploymentami, service, ingress, secretami, limitami i politykami.
- Dobrze integruje się z cert-manager, ingress controllerami, Prometheus, OpenTelemetry i policy-as-code.
- Pozwala skalować runtime niezależnie od control plane.
- Umożliwia stopniowe dojście do zaawansowanej izolacji przez node poole, tainty, tolerations lub dedykowane klastry.

## Konsekwencje negatywne

- Kubernetes jest złożony operacyjnie i łatwo o błędne konfiguracje bezpieczeństwa.
- Izolacja namespace nie jest izolacją równą osobnemu klastrowi.
- Wymaga dojrzałego procesu patchowania node'ów, kontrolowania RBAC i monitorowania runtime.
- Błędy orchestratora mogą tworzyć zasoby w złym namespace lub z nadmiernymi uprawnieniami.
- Koszty i limity zasobów muszą być aktywnie zarządzane.

## Alternatywy

- Nomad: prostszy scheduler, ale mniejszy ekosystem ingress/certyfikaty/polityki.
- Serverless containers: mniej operacji, ale słabsza kontrola izolacji i portability.
- VM per tenant: mocniejsza izolacja, ale większy koszt i wolniejszy provisioning.
- Dedykowany klaster per tenant: lepsza izolacja, ale za drogie i zbyt złożone dla MVP.

## Wpływ na bezpieczeństwo

- Workloady klientów są niezaufane i muszą być uruchamiane z restrykcyjnymi politykami.
- Wymagane są Pod Security Admission, NetworkPolicy, ResourceQuota, LimitRange, minimalne RBAC i oddzielne service accounty.
- Zabronione są privileged containers, hostPath, hostNetwork, hostPID, hostIPC oraz dostęp do socketu runtime.
- Control plane nie może być dostępny z tenant workloadów.
- Należy stosować skanowanie obrazów, monitoring anomalii i regularny audit konfiguracji klastra.
