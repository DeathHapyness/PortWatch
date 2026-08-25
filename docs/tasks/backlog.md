# Backlog de tarefas entre agentes

Mantido pelo Lead. Cada item vira um branch `agent/<área>/<slug>` isolado
(worktree próprio, ver `CLAUDE.md`) quando um agente pega a tarefa. Depois de
pronto, PR/revisão do Lead antes do merge em `main` — nenhum agente faz merge
do próprio trabalho.

## Em aberto

### 1. Backend — autenticação do WebSocket via primeira mensagem
- **Branch sugerido:** `agent/backend/ws-first-message-auth`
- **Dono sugerido:** Codex
- **Contexto:** ADR-0006 (`docs/adr/0006-websocket-first-message-auth.md`)
  decide como destravar o consumo do WS `/api/v1/events` a partir do
  browser (token não pode ir na URL nem em header custom).
- **Escopo:**
  - Em `apps/backend/src/portwatch_backend/api/events.py`: aceitar a
    conexão, aguardar até 5s por uma primeira mensagem de texto
    `{"token": "..."}`, validar com `validate_api_token()`
    (`core/auth.py`, já existe e é reaproveitável). Fechar com
    `code=1008` se inválido/ausente/timeout — mesmo código já usado hoje
    para o path de header ausente.
  - Manter o path por header `Authorization` funcionando como fallback
    (não quebrar `tests/test_events.py` existente).
  - Testes novos: sucesso via primeira mensagem, token errado via
    primeira mensagem, timeout sem nenhuma mensagem.
  - `ruff check`, `ruff format --check`, `mypy src`, `pytest` verdes
    antes de abrir para revisão.

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
