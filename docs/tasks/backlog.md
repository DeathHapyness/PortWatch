# Backlog de tarefas entre agentes

Mantido pelo Lead. Cada item vira um branch `agent/<área>/<slug>` isolado
(worktree próprio, ver `CLAUDE.md`) quando um agente pega a tarefa. Depois de
pronto, PR/revisão do Lead antes do merge em `main` — nenhum agente faz merge
do próprio trabalho.

## Concluído (resumo — detalhes no histórico do git)

WebSocket com auth via primeira mensagem + hardening e desligamento
gracioso, com limite de assinantes simultâneos por processo; métricas
Prometheus; logs estruturados JSON com redação de segredos; validação de
bounds em toda `Settings`; `/health/ready` e `/api/v1/system/summary`
servidos a partir de uma visão-resumo pré-computada (`SnapshotOverview`);
lookup de container/rede por id/nome indexado O(1)
(`find_container`/`find_network`); leituras seletivas por coleção sem
clonar dados não relacionados; validação de shape nas respostas do Docker e
do netprobe, com o cliente do netprobe agora usando streaming real para
abortar respostas grandes durante a transferência; orçamento de tempo e
limites de contagem por ciclo do Collector (ADR-0007); `X-Request-Id`
client-supplied restrito antes de entrar em logs/resposta;
`Cache-Control: no-store` em `/api/v1/*`/`/metrics`; cabeçalhos
`X-Content-Type-Options`/`X-Frame-Options` em toda resposta; isolamento de
falhas no cleanup do cliente Docker. Frontend consumindo o WebSocket,
autenticando REST com o mesmo token, **token de runtime via `ApiTokenDialog`
guardado em `localStorage`** (ver abaixo), e renderizando com segurança um
`detail` de erro 422 em formato de array. Publicação pública: LICENSE MIT,
`CONTRIBUTING.md`, `.github/SECURITY.md`, issue/PR templates, modelo de
ameaça e guia de implantação segura (`docs/security/`), checklist de
release (`docs/release/`), Dockerfile de produção hardened para o backend,
CI com `permissions: contents: read`, timeouts por job e instalação
reproduzível (`uv sync --locked`, `packageManager` pinado), Dependabot.
Tudo revisado pelo Lead (testes adicionados onde faltavam — ver
[[multi-agent-roster]]) e mergeado em `main`.

### Frontend — token de runtime em vez de embutido no build (concluído 2026-08-26)
Implementado: `ApiTokenDialog` (ícone de chave no header) grava o token em
`localStorage` via `lib/config.ts`'s `setApiToken`; `getApiToken()` lê de lá
primeiro, com `VITE_API_TOKEN` como fallback de conveniência para dev local
(não mais o caminho recomendado). Ver README, seção "Ressalva de segurança
anterior, corrigida".

## Em aberto

Nenhum item bloqueador conhecido no momento. Ver
`docs/release/public-release-checklist.md` para os itens que ainda faltam
antes de um release público formal (imagem de produção do frontend, compose
de produção, quickstart validado do zero, scans de dependência/imagem,
branch protection, etc. — a maioria fora do escopo de código deste
backlog).
