# PortWatch

Plataforma de monitoramento de homelab — Docker, containers e portas de rede.

Status atual: **Fase 2 — Project Foundation**. Existe um esqueleto de backend
(FastAPI, contrato OpenAPI inicial, sem lógica real ainda) e de frontend
(React + Vite), mas nenhuma funcionalidade de monitoramento real — isso é a
Fase 3 em diante. Arquitetura completa e roadmap:
https://claude.ai/code/artifact/b41be8c8-2963-4ef8-a4f7-b984b68407a8

Decisões arquiteturais registradas em `docs/adr/`.

## Estrutura

```
apps/backend/   FastAPI + Collector (mesmo processo, ver ADR-0001), uv
apps/web/       React + TypeScript + Vite + Tailwind + shadcn/ui
docs/adr/       Architecture Decision Records
infra/dev/      sandbox Docker isolado para desenvolvimento
```

## Requisitos de desenvolvimento

- Node 22 LTS (via `nvm`, ver `.nvmrc`)
- pnpm (via `corepack`, já habilitado pelo Node)
- Python 3.12 + [`uv`](https://docs.astral.sh/uv/)
- Docker + Docker Compose (contexto **local**, nunca o do homelab de produção)

## Sandbox de desenvolvimento

Todo o desenvolvimento e teste roda contra um Docker isolado nesta máquina —
nunca contra o Docker de produção do homelab (ver `CLAUDE.md`).

```sh
make dev-up      # sobe o sandbox (com verificação de segurança prévia)
make dev-status  # lista o que está rodando no sandbox
make dev-down    # derruba e limpa o sandbox
```

`infra/dev/guard.sh` recusa subir a stack se o Docker "de destino" não parecer
ser um Docker de desenvolvimento local vazio — ver comentários no script.

## Rodando localmente

```sh
# Backend — http://127.0.0.1:8000, docs em /docs, contrato em /openapi.json
cd apps/backend
uv run uvicorn portwatch_backend.app:app --reload --port 8000

# Frontend — http://127.0.0.1:5173, proxy /api/* -> backend acima
cd apps/web
pnpm install
pnpm dev
```

Checagens de qualidade:

```sh
cd apps/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
cd apps/web     && pnpm run lint && pnpm run format:check && pnpm run build
```
