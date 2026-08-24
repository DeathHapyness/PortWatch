# PortWatch

Plataforma de monitoramento de homelab — Docker, containers e portas de rede.

Status atual: **Fase 4 — API real (concluída)**, iniciando Fase 5/6. Backend:
o Collector coleta containers, redes e portas do sandbox via
`docker-socket-proxy`/`netprobe`, publica snapshots atômicos em memória e
expõe readiness real; todas as rotas (`containers`, `networks`, `system`,
`ports`) leem esses snapshots — nenhuma retorna mais dados de exemplo.
Autenticação por token estático (ADR-0004), erros no contrato RFC 7807
completo (incluindo validação 422 e `request_id` por requisição), e labels/env
de containers redigidos por padrão (PW-03). WebSocket `/api/v1/events`
transmite invalidações de snapshot em tempo real (token via header
`Authorization`, mesmo esquema do REST — não usável a partir de um browser
puro sem um mecanismo adicional, já que a WebSocket API nativa não permite
headers customizados; pendente de decisão antes da integração no frontend).
Frontend: dashboard funcional (Overview/Containers/Networks/Ports) já
consumindo as APIs REST via TanStack Query, ainda por poll (não consome o
WebSocket ainda). Testes E2E (`apps/backend/tests/e2e/`, `make test-e2e`)
sobem o sandbox real e validam o Collector fim a fim através do
`docker-socket-proxy`/`netprobe` de verdade. Falta: o frontend consumir o
WebSocket, e observabilidade (Fase 9 — métricas Prometheus). Arquitetura
completa e roadmap:
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

Além do fixture inerte (`fixture-web`), o sandbox inclui os dois serviços usados
pelo Collector, ambos publicados só em `127.0.0.1` para o backend nativo
(rodando fora do Docker) alcançar:

- `docker-socket-proxy` (`127.0.0.1:2375`) — único container com o socket
  Docker real montado, restrito a GET (ver
  `docs/adr/0003-docker-access-isolation.md`).
- `netprobe` (`127.0.0.1:8088`) — utilitário mínimo que lê `/proc/net/*` do
  host para reportar portas ocupadas; único componente com
  `network_mode: host`, sem nenhum acesso ao socket Docker. Contrato HTTP em
  `infra/netprobe/README.md`.

## Rodando localmente

```sh
# Backend — http://127.0.0.1:8000, docs em /docs, contrato em /openapi.json
cd apps/backend
# Se o sandbox de dev estiver de pé (make dev-up), aponte para os serviços
# de infra via loopback (fora disso, os defaults deixam os recursos
# desabilitados — ver core/config.py):
export PORTWATCH_DOCKER_PROXY_URL=http://127.0.0.1:2375
export PORTWATCH_NETPROBE_URL=http://127.0.0.1:8088
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

`uv run pytest` acima nunca toca Docker (exclui o marker `e2e` por padrão —
ver `pyproject.toml`). Para rodar a suíte E2E de verdade contra o sandbox
real (sobe/derruba a stack sozinha, mesmo guard do `make dev-up`):

```sh
make test-e2e
```
