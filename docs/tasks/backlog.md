# Backlog de tarefas entre agentes

Mantido pelo Lead. Cada item vira um branch `agent/<área>/<slug>` isolado
(worktree próprio, ver `CLAUDE.md`) quando um agente pega a tarefa. Depois de
pronto, PR/revisão do Lead antes do merge em `main` — nenhum agente faz merge
do próprio trabalho.

## Concluído

### 1. Backend — autenticação do WebSocket via primeira mensagem ✅
Implementado por Codex em `agent/backend/ws-first-message-auth` (commit
`c83c25a`), revisado pelo Lead e mergeado em `main` (merge commit, 2026-08-25).
`apps/backend/src/portwatch_backend/api/events.py` agora aceita a conexão e
aguarda até 5s por `{"token": "..."}` como primeira mensagem quando não há
header `Authorization` (browser); o header continua funcionando como
fallback. Testes em `tests/test_events.py` cobrem sucesso, token errado e
timeout. Quality gates (ruff/format/mypy/pytest/e2e) verdes.

### 2. Observabilidade — métricas Prometheus (Fase 9) ✅
Implementado pelo Lead (`agent/backend/observability-metrics`, commit
`f448232`), com dois follow-ups de correção do Codex, ambos revisados e
mergeados: cardinalidade de rotas não encontradas (`agent/backend/
metrics-cardinality-errors`, `5f2bd26`) e — junto — logs estruturados em
JSON (`agent/backend/structured-logging`, `5afee6d`, ver item 4). `GET
/metrics` protegido pelo mesmo bearer token; `core/metrics.py`.

### 3. Frontend — consumo do WebSocket no dashboard ✅
Implementado pelo Lead. `apps/web/src/lib/useSnapshotEvents.ts`: abre
`/api/v1/events`, manda `{"token": ...}` (via `VITE_API_TOKEN`, ver
`lib/config.ts`) como primeira mensagem (ADR-0006), invalida
`portwatchQueryKeys.all` em cada `snapshot.updated`, reconecta com backoff
exponencial (1s→30s). `vite.config.ts` ganhou `ws: true` no proxy do dev
server. Testes em `lib/useSnapshotEvents.test.tsx`. `pnpm lint/format:check/
build/test` verdes.

### 4. Observabilidade — logs estruturados JSON (Fase 9) ✅
Implementado por Codex (auto-iniciado) em `agent/backend/structured-logging`
(commit `5afee6d`), revisado pelo Lead e mergeado. `core/logging.py`: JSON
formatter com schema fixo (não serializa `extra` arbitrário), `request_id`
correlacionado via `ContextVar` (bind/reset em `request_id_middleware`),
redação best-effort de `Bearer`/`token=`/`"token":"..."` nas mensagens e
exceções. Testes em `tests/test_logging.py`.

## Em aberto

Nenhum item específico no momento — próximas tarefas a definir conforme
Codex/Copilot ficarem livres. Copilot está focado em cobertura de testes
adicional por pedido direto do usuário (fora deste backlog formal).
