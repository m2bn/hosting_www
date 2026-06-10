# ADR-0010: Monorepo jako struktura projektu

## Status

Accepted

## Kontekst

Platforma będzie składać się z backendu control plane, dashboardu, infrastruktury, manifestów Kubernetes, bibliotek wspólnych, dokumentacji, testów, narzędzi CI/CD i potencjalnie CLI. Na etapie MVP ważna jest spójność zmian między komponentami i szybka praca zespołu.

## Decyzja

Projekt prowadzimy jako monorepo.

## Konsekwencje pozytywne

- Ułatwia atomowe zmiany obejmujące backend, frontend, infrastrukturę i dokumentację.
- Upraszcza odkrywanie kodu, standardów i zależności między modułami.
- Pozwala utrzymać wspólny pipeline CI/CD, standardy lintingu, testów i security scanning.
- Ułatwia wersjonowanie kontraktów API i typów współdzielonych.
- Zmniejsza narzut organizacyjny w MVP.

## Konsekwencje negatywne

- CI/CD może stać się wolne bez selektywnego uruchamiania testów.
- Granice własności modułów mogą się zacierać.
- Repozytorium może rosnąć szybko i wymagać dyscypliny struktury katalogów.
- Uprawnienia do repo są mniej granularne niż w wielu osobnych repozytoriach.

## Alternatywy

- Polyrepo: lepsza separacja własności i uprawnień, ale większy koszt koordynacji zmian.
- Monorepo tylko dla aplikacji, infrastruktura osobno: lepsza separacja IaC, ale trudniejsze atomowe zmiany.
- Repo per komponent: dobre dla dużych niezależnych zespołów, za ciężkie dla MVP.

## Wpływ na bezpieczeństwo

- Monorepo musi mieć CODEOWNERS lub równoważne reguły review dla obszarów krytycznych.
- CI/CD musi uruchamiać secret scanning, dependency scanning, SAST i policy-as-code.
- Sekrety nie mogą być przechowywane w repo; wymagane są pre-commit lub pipeline checks.
- Zmiany w security baseline, politykach Kubernetes, billing, auth i RBAC powinny wymagać przeglądu właścicieli bezpieczeństwa.
- Uprawnienia do repo i branch protection muszą być skonfigurowane zgodnie z least privilege.
