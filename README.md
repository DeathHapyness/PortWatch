# PortWatch

Plataforma de monitoramento de homelab — Docker, containers e portas de rede.

**Status:** funcional e pronto para uso pessoal em loopback hoje. Todos os
gaps essenciais do roadmap original estão fechados; o projeto está em
preparação ativa para publicação pública sob licença MIT — o que falta para
esse próximo passo (não para o uso atual) está rastreado em
[`docs/release/public-release-checklist.md`](docs/release/public-release-checklist.md).
Arquitetura completa e roadmap:
https://claude.ai/code/artifact/b41be8c8-2963-4ef8-a4f7-b984b68407a8.
Modelo de ameaça, guia de implantação segura e referência de configuração em
[`docs/README.md`](docs/README.md).

**Backend.** O Collector coleta containers, redes e portas do sandbox via
`docker-socket-proxy`/`netprobe`, publica snapshots atômicos em memória
(agora com índice O(1) para lookup por id/nome — `collector/state.py`'s
`find_container`/`find_network` — e uma visão-resumo pré-computada,
`SnapshotOverview`, para `/health/ready` e `/api/v1/system/summary`) e
expõe readiness real. Todas as rotas leem esses snapshots — nenhuma retorna
dados de exemplo. Nem o Docker nem o netprobe são confiados às cegas: as
respostas de ambos são validadas por shape antes de virar estado interno
(`DockerPayloadError`, `collector/netprobe_client.py`), e o cliente do
netprobe agora usa `httpx.stream` para abortar uma resposta acima de 1 MiB
durante a transferência, não depois de já ter baixado tudo. Um ciclo do
Collector tem orçamento de tempo e limites de contagem configuráveis
(`PORTWATCH_COLLECTOR_CYCLE_BUDGET_SECONDS`/`MAX_CONTAINERS`/`MAX_NETWORKS`
— ADR-0007); estourar qualquer um falha o ciclo sem publicar um snapshot
truncado. `core/config.py` valida limites em tudo que vem de variável de
ambiente, incluindo o limite de assinantes WebSocket simultâneos
(`PORTWATCH_WEBSOCKET_MAX_SUBSCRIBERS`). Autenticação por token estático
(ADR-0004) com um `X-Request-Id` client-supplied agora restrito a um token
ASCII curto antes de entrar em logs/header de resposta; erros no contrato
RFC 7807 completo; labels/env de containers redigidos por padrão (PW-03).
Respostas de `/api/v1/*` e `/metrics` levam `Cache-Control: no-store`; todo
response leva `X-Content-Type-Options: nosniff` e `X-Frame-Options: DENY`.
Imagem de container de produção hardened em `apps/backend/Dockerfile`
(non-root, multi-stage, `--no-server-header`, recusa iniciar fora de
loopback sem token).

**Deploy.** `apps/web/Dockerfile` (nginx-unprivileged, non-root, serve o
bundle estático e faz proxy de `/api/*` — incluindo o upgrade de WebSocket
de `/api/v1/events` — para o backend) e
`infra/prod/docker-compose.prod.yml` (backend + frontend + docker-socket-proxy,
os três non-root/`read_only`/`cap_drop: ALL`/com limites de CPU-memória-PIDs,
socket real montado só no proxy) sobem o PortWatch inteiro containerizado.
TLS não está incluído — coloque um reverse proxy próprio na frente antes de
expor fora de loopback. Netprobe fica de fora desse compose de propósito
(namespace de rede incompatível com um backend containerizado — ver
`infra/prod/README.md`); use-o via sandbox de dev/backend nativo se precisar
de visibilidade de portas do host. Detalhes em `infra/prod/README.md` e
[`docs/release/public-release-checklist.md`](docs/release/public-release-checklist.md)
para o que ainda falta antes disso ser um release público.

**WebSocket.** `/api/v1/events` transmite invalidações de snapshot em tempo
real com desligamento gracioso; autentica via header `Authorization`
(clientes não-browser) ou, quando ausente, via `{"token": "..."}` como
primeira mensagem da conexão, com limites de tamanho de mensagem/token e
rejeição de payload malformado — ver
`docs/adr/0006-websocket-first-message-auth.md`. Conexões simultâneas são
limitadas por processo (`PORTWATCH_WEBSOCKET_MAX_SUBSCRIBERS`, padrão 128);
acima do limite, a conexão já autenticada é fechada com 1013.

**Frontend.** Dashboard funcional (Overview/Containers/Networks/Ports)
consumindo as APIs REST via TanStack Query e `/api/v1/events`
(`useSnapshotEvents`) para invalidar as queries assim que o Collector
publica um novo snapshot — o poll continua como fallback. O token da API é
digitado em runtime pelo ícone de chave no header (`ApiTokenDialog`) e
guardado só em `localStorage` deste navegador — nunca embutido no bundle
JS compartilhado (ver ressalva de segurança, agora corrigida, abaixo). Uma
resposta de validação (422, `detail` como array de erros do FastAPI, não
string) é formatada com segurança em vez de quebrar a renderização
(`formatProblemDetail`, `lib/api.ts`).

Testes E2E (`apps/backend/tests/e2e/`, `make test-e2e`) sobem o sandbox
real e validam o Collector fim a fim através do `docker-socket-proxy`/
`netprobe` de verdade. Observabilidade: métricas Prometheus em
`GET /metrics` (protegido pelo mesmo bearer token, cardinalidade de rota
limitada, sem cache) e logs estruturados em JSON com `request_id`
correlacionado por requisição e redação best-effort de segredos; tracing
(OpenTelemetry) segue fora do MVP por decisão de escopo.

**Ressalva de segurança anterior, corrigida em 2026-08-26:** o token do
frontend costumava ser embutido em texto puro no bundle JS de produção
(`VITE_API_TOKEN`, comportamento padrão do Vite) — inofensivo em loopback,
mas extraível por qualquer um que carregasse a página fora dele. Corrigido:
o token agora é digitado em runtime via `ApiTokenDialog` (ícone de chave no
header) e guardado em `localStorage` por navegador. Detalhes completos em
[`docs/security/threat-model.md`](docs/security/threat-model.md).

Decisões arquiteturais registradas em `docs/adr/`. Para publicação pública,
ver `CONTRIBUTING.md`, `.github/SECURITY.md` e `docs/README.md`.

## Licença

[MIT](LICENSE).

## Estrutura

```
apps/backend/   FastAPI + Collector (mesmo processo, ver ADR-0001), uv, Dockerfile de produção
apps/web/       React + TypeScript + Vite + Tailwind + shadcn/ui, Dockerfile de produção
docs/adr/       Architecture Decision Records
docs/security/  modelo de ameaça e guia de implantação segura
docs/release/   checklist de release público
infra/dev/      sandbox Docker isolado para desenvolvimento
infra/prod/     Compose de produção (backend + frontend + docker-socket-proxy)
infra/netprobe/ utilitário host-only de portas ocupadas
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
# Referência completa de todas as variáveis, defaults e limites:
# docs/reference/configuration.md

# Frontend — http://127.0.0.1:5173, proxy /api/* -> backend acima
# (proxy inclui upgrade de WebSocket para /api/v1/events)
cd apps/web
pnpm install
pnpm dev
```

Se o backend tiver um token configurado (`PORTWATCH_API_TOKEN`), digite-o
no dashboard: ícone de chave no header → cola o token → salva (recarrega a
página). Ele fica só em `localStorage` deste navegador, nunca no bundle
JS. `VITE_API_TOKEN` (env var no build) continua funcionando como atalho
de conveniência para desenvolvimento local, mas não é mais necessário nem
recomendado.

Checagens de qualidade:

```sh
cd apps/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
cd apps/web     && pnpm run lint && pnpm run format:check && pnpm run test && pnpm run build
python -m unittest discover -s infra/netprobe/tests -v   # mudanças em infra/netprobe
```

`uv run pytest` acima nunca toca Docker (exclui o marker `e2e` por padrão —
ver `pyproject.toml`). Para rodar a suíte E2E de verdade contra o sandbox
real (sobe/derruba a stack sozinha, mesmo guard do `make dev-up`):

```sh
make test-e2e
```

Para construir e validar a imagem de produção do backend localmente
(Docker local, nunca o homelab):

```sh
cd apps/backend && docker build -t portwatch-backend .
docker run --rm -p 8000:8000 -e PORTWATCH_API_TOKEN=<algo> portwatch-backend
curl http://127.0.0.1:8000/health
```
