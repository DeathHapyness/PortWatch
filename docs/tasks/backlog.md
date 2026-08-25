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

## Em aberto

### 2. Frontend — consumo do WebSocket no dashboard
- **Branch sugerido:** `agent/frontend/websocket-live-updates`
- **Dono sugerido:** Copilot
- **Contexto:** o dashboard (`apps/web`) hoje só faz poll via TanStack
  Query; o backend já publica `snapshot.updated` em `/api/v1/events`
  (ver ADR-0006 para o protocolo de auth a seguir).
- **Escopo:**
  - Client WebSocket para `/api/v1/events`: abrir o socket, mandar
    `{"token": "<api token atual>"}` como primeira mensagem, tratar
    mensagens subsequentes como eventos `snapshot.updated`.
  - Ao receber um evento, invalidar/atualizar as queries do TanStack
    Query correspondentes em vez de depender só do poll atual.
  - Reconexão em disconnect (backoff simples).
  - Testes (vitest) cobrindo handshake, evento de invalidação e
    reconexão.
  - `pnpm lint`, `pnpm format:check`, `pnpm build`, `pnpm test` verdes
    antes de abrir para revisão.

## Depois disso (fila, sem dono ainda)

### 3. Observabilidade — métricas Prometheus (Fase 9)
Ver `README.md` (seção Status) e `CLAUDE.md` (Observabilidade: "logs
estruturados + métricas Prometheus no MVP"). Ainda não iniciado.
