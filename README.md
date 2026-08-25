# PortWatch

Plataforma de monitoramento de homelab — Docker, containers e portas de rede.

Status atual: **Fase 4 — API real (concluída)**, mais uma rodada de
hardening de segurança/robustez sobre a Fase 9. Backend: o Collector coleta
containers, redes e portas do sandbox via `docker-socket-proxy`/`netprobe`,
publica snapshots atômicos em memória e expõe readiness real (derivada das
mesmas `Settings` capturadas no startup, não recalculada a cada request);
todas as rotas (`containers`, `networks`, `system`, `ports`) leem esses
snapshots — nenhuma retorna mais dados de exemplo. Nem o Docker nem o
netprobe são mais confiados às cegas: as respostas de ambos são validadas
por shape antes de virar estado interno (ver `collector/parsing.py`'s
`DockerPayloadError` e `collector/netprobe_client.py`), então um
`docker-socket-proxy` comprometido ou um netprobe com bug não corrompe o
snapshot nem derruba o Collector. `core/config.py` valida limites em tudo
que vem de variável de ambiente (portas, intervalo de poll, URLs,
log level, token). Autenticação por token estático (ADR-0004), erros no
contrato RFC 7807 completo (incluindo validação 422 e `request_id` por
requisição), e labels/env de containers redigidos por padrão (PW-03).
WebSocket `/api/v1/events` transmite invalidações de snapshot em tempo real
com desligamento gracioso (fecha com 1001, não derruba a conexão, quando a
app para); autentica via header `Authorization` (clientes não-browser) ou,
quando ausente, via `{"token": "..."}` como primeira mensagem da conexão
(browsers, que não podem setar headers customizados no handshake), com
limites de tamanho de mensagem/token e rejeição de payload malformado — ver
`docs/adr/0006-websocket-first-message-auth.md`. Frontend: dashboard
funcional (Overview/Containers/Networks/Ports) consumindo as APIs REST via
TanStack Query (autenticadas com o mesmo bearer token quando configurado —
ver ressalva de segurança abaixo) e também `/api/v1/events`
(`useSnapshotEvents`) para invalidar as queries assim que o Collector
publica um novo snapshot — o poll continua como fallback. Testes E2E
(`apps/backend/tests/e2e/`, `make test-e2e`) sobem o sandbox real e validam
o Collector fim a fim através do `docker-socket-proxy`/`netprobe` de
verdade. Observabilidade (Fase 9): métricas Prometheus em `GET /metrics`
(protegido pelo mesmo bearer token, cardinalidade de rota limitada — ver
`core/metrics.py`) — requests HTTP por rota/status e ciclos do Collector
(duração, sucesso/falha, geração/containers/portas do snapshot atual) — e
logs estruturados em JSON com `request_id` correlacionado por requisição e
redação best-effort de segredos (`core/logging.py`); tracing (OpenTelemetry)
segue fora do MVP por decisão de escopo. Gaps essenciais do roadmap
original estão fechados — o que resta é maturidade (mais cobertura de
testes, pequenas manutenções). Arquitetura completa e roadmap:
https://claude.ai/code/artifact/b41be8c8-2963-4ef8-a4f7-b984b68407a8

**Ressalva de segurança conhecida, não corrigida:** `VITE_API_TOKEN` é
embutido em texto puro no bundle JS do frontend no build (comportamento
padrão do Vite para `import.meta.env.VITE_*` — confirmado inspecionando
`dist/assets/*.js`). Em loopback isso não importa (quem tem acesso ao
processo já tem acesso ao valor da env var). Mas no cenário que o
ADR-0004 prevê como exigindo token — exposição em LAN/remota — qualquer
um que carregue a página do dashboard consegue extrair o token direto do
JS servido, o que o torna inútil como segredo nesse cenário (continua
barrando acesso direto à API por quem nunca carregou o frontend, mas não
protege contra quem carregou). Mitigação hoje: a própria ADR-0004 já
pressupõe uma camada de acesso própria do usuário na frente (Tailscale,
Authelia) para esse cenário. Correção real ficaria em trocar o token
embutido no build por um token digitado em runtime e guardado em
`localStorage` (por navegador, nunca no bundle compartilhado) — não
implementado ainda, ver `docs/tasks/backlog.md`.

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
# (proxy inclui upgrade de WebSocket para /api/v1/events)
cd apps/web
# Só necessário se o backend tiver um token configurado — usado tanto nas
# chamadas REST (header Authorization) quanto na primeira mensagem do
# WebSocket (ADR-0006). Ver a ressalva de segurança acima antes de usar
# isso fora de loopback: este valor é embutido em texto puro no bundle JS
# do build de produção.
export VITE_API_TOKEN=<mesmo valor de PORTWATCH_API_TOKEN, se configurado>
pnpm install
pnpm dev
```

Checagens de qualidade:

```sh
cd apps/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
cd apps/web     && pnpm run lint && pnpm run format:check && pnpm run test && pnpm run build
```

`uv run pytest` acima nunca toca Docker (exclui o marker `e2e` por padrão —
ver `pyproject.toml`). Para rodar a suíte E2E de verdade contra o sandbox
real (sobe/derruba a stack sozinha, mesmo guard do `make dev-up`):

```sh
make test-e2e
```
