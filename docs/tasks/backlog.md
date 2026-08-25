# Backlog de tarefas entre agentes

Mantido pelo Lead. Cada item vira um branch `agent/<área>/<slug>` isolado
(worktree próprio, ver `CLAUDE.md`) quando um agente pega a tarefa. Depois de
pronto, PR/revisão do Lead antes do merge em `main` — nenhum agente faz merge
do próprio trabalho.

## Concluído (resumo — detalhes no histórico do git)

WebSocket com auth via primeira mensagem + hardening (tamanho de
mensagem/token, campos duplicados/inesperados) e desligamento gracioso;
métricas Prometheus (`GET /metrics`, cardinalidade limitada); logs
estruturados JSON com redação de segredos; validação de bounds em toda
`Settings` (portas, poll interval, URLs, log level, token); `/health/ready`
usando as settings capturadas no startup em vez de reler a cada request;
validação de shape nas respostas do Docker (`DockerPayloadError`) e do
netprobe antes de virar estado interno; frontend consumindo o WebSocket
(`useSnapshotEvents`) e autenticando as chamadas REST com o mesmo bearer
token; CI rodando a suíte de testes do frontend (antes só lint/build).
Tudo revisado pelo Lead (testes adicionados onde faltavam — ver
[[multi-agent-roster]]) e mergeado em `main`.

## Em aberto

### Frontend — token de runtime em vez de embutido no build
- **Contexto:** achado da revisão de segurança de 2026-08-25 (ver README,
  seção "Ressalva de segurança conhecida"). `VITE_API_TOKEN` é embutido em
  texto puro no bundle JS pelo Vite — inspecionado diretamente em
  `dist/assets/*.js` após um build com o valor setado. Em loopback isso não
  importa; no cenário que a própria ADR-0004 prevê como exigindo token
  (exposição em LAN/remota), qualquer um que carregue a página consegue
  extrair o token do JS servido — deixa de funcionar como segredo nesse
  cenário específico (a API continua barrando quem nunca carregou o
  frontend, mas não quem carregou).
- **Escopo:** trocar o token embutido no build por um campo simples na UI
  (ex.: um diálogo/settings) onde o usuário cola o token uma vez; guardar em
  `localStorage` (por navegador, nunca no bundle compartilhado — mesmo
  padrão que `Header.tsx` já usa para o tema). `api.ts`/`useSnapshotEvents.ts`
  passam a ler de lá em vez de `getApiToken()`/`import.meta.env`. Não é
  urgente para uso em loopback (o caso de uso atual); vale antes de
  recomendar exposição em LAN/remota para qualquer usuário.
- **Dono sugerido:** ainda sem dono — Codex está temporariamente em
  `agent/website/rework` a pedido do usuário, volta para o backend depois.
