# ADR-0006: MinIO/S3-compatible storage jako storage plików

## Status

Accepted

## Kontekst

Platforma potrzebuje storage dla uploadów, artefaktów deploymentów, backupów, eksportów logów i potencjalnie plików klientów. Storage powinien mieć standardowe API, dobre wsparcie narzędziowe, polityki dostępu, szyfrowanie, lifecycle i możliwość uruchamiania lokalnie oraz w chmurze.

## Decyzja

Używamy storage zgodnego z S3 API. W środowiskach własnych lub lokalnych dopuszczamy MinIO, a w chmurze zarządzany S3-compatible object storage.

## Konsekwencje pozytywne

- S3 API jest standardem ekosystemu i ułatwia przenoszenie między providerami.
- MinIO pozwala odtworzyć środowisko lokalne i staging bez zależności od konkretnej chmury.
- Object storage dobrze pasuje do artefaktów, uploadów, backupów i eksportów.
- Wspiera lifecycle policies, wersjonowanie, szyfrowanie i pre-signed URLs.
- Ułatwia rozdzielenie storage aplikacyjnego od bazy danych.

## Konsekwencje negatywne

- MinIO w produkcji wymaga własnej odpowiedzialności operacyjnej, HA, backupu i monitoringu.
- S3-compatible API nie zawsze oznacza pełną zgodność zachowania między providerami.
- Błędna konfiguracja bucket policy może prowadzić do publicznego wycieku danych.
- Pre-signed URLs wymagają ostrożnej kontroli czasu życia i zakresu.

## Alternatywy

- AWS S3 bez warstwy kompatybilności: bardzo dojrzały, ale wiąże mocniej z AWS.
- Google Cloud Storage/Azure Blob: dobre usługi, ale mniej neutralne względem S3 API.
- Storage w PostgreSQL: nieodpowiednie dla większych plików i artefaktów.
- Shared filesystem/NFS: prostsze lokalnie, ale słabsze dla skalowania i multi-tenant isolation.

## Wpływ na bezpieczeństwo

- Buckety muszą mieć public access block albo równoważne zabezpieczenia.
- Obiekty muszą być namespacowane tenantem i projektem.
- Dostęp do plików musi być autoryzowany przez control plane, a pre-signed URLs muszą mieć krótkie TTL.
- Uploady wymagają limitów rozmiaru, walidacji typu, bezpiecznych nazw i ochrony przed aktywną treścią.
- Backupy w object storage muszą być szyfrowane, mieć ograniczony dostęp i testy restore.
