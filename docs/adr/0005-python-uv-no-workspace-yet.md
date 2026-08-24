# ADR-0005 — `uv` sem workspace até existir um segundo pacote Python

## Status
Aceito.

## Contexto
O blueprint original sugeria um `uv` workspace para acomodar Collector como
pacote separado. A ADR-0001 uniu API e Collector num único processo/pacote
(`portwatch-backend`) — hoje existe apenas um pacote Python no repositório.

## Decisão
`apps/backend` é um projeto `uv` autônomo (seu próprio `pyproject.toml` e
`.venv`), sem um `pyproject.toml` de workspace na raiz do repositório.

## Consequências
- Menos um nível de configuração para manter enquanto só há um pacote.
- Se um segundo pacote Python surgir (ex.: uma lib de domínio compartilhada,
  ou o Collector for desacoplado no futuro — ver ADR-0001), introduzir um
  `uv` workspace na raiz é direto e não exige reestruturar `apps/backend`.
