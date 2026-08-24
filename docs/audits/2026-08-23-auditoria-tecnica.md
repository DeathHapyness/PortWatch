# Relatório de auditoria técnica — PortWatch

**Data:** 23/08/2026  
**Escopo:** estado observado durante desenvolvimento concorrente na branch `main`  
**Método:** análise somente-leitura; nenhum arquivo de implementação, commit,
branch, container ou configuração Docker foi alterado durante a auditoria.

> Este documento é um retrato temporal. O Claude Code estava modificando o
> projeto durante a análise; alguns achados documentais podem ter sido corrigidos
> antes da criação deste arquivo. O blueprint externo referenciado pelo projeto
> não estava acessível na sessão, portanto as divergências foram avaliadas contra
> `README.md`, `AGENTS.md`, `CLAUDE.md` e os ADRs locais.

## Resumo executivo

- **Critical:** 1
- **High:** 5
- **Medium:** 7
- **Low:** 4
- **Sugestões arquiteturais:** 4
- Nenhuma race condition executável foi encontrada no código atual porque o
  Collector ainda não existe, mas há riscos concretos no desenho de estado
  compartilhado e no guard do Docker.
- Frontend passou em lint, formatação e type-check.
- Compose passou na validação sintática.
- Ruff passou.
- Pytest e mypy não iniciaram porque o `.venv` existente referenciava um runtime
  temporário removido.

## Critical

### PW-01 — `dev-down` ignora completamente o guard de segurança

**Localização:** `Makefile:12-13`, em contraste com `infra/dev/guard.sh:7`.

**Motivo:** `dev-up` depende de `dev-guard`, mas `dev-down` executa diretamente
`docker compose -f $(DEV_COMPOSE) down -v`. O comentário do guard diz que ele
deveria ser chamado antes de subir ou derrubar o sandbox.

**Impacto:** se o contexto ativo ou `DOCKER_HOST` apontar acidentalmente para
outro daemon, `make dev-down` pode parar e remover containers, redes e volumes
do projeto Compose correspondente. Isso contradiz diretamente a regra de nunca
alterar o homelab.

**Correção recomendada:** fazer `dev-down` depender de `dev-guard` e aplicar o
guard a toda operação que crie, pare ou remova recursos. Idealmente, guard e
Compose devem usar um endpoint/contexto explicitamente resolvido e imutável.

## High

### PW-02 — Autenticação documentada, mas inexistente

**Localização:** `apps/backend/src/portwatch_backend/core/config.py:28-30`,
`apps/backend/src/portwatch_backend/app.py:17-46` e
`docs/adr/0004-simple-static-token-auth.md:12-16`.

**Motivo:** existe `api_token`, e o ADR determina token bearer obrigatório para
exposição fora de loopback, mas nenhuma rota ou dependência valida
`Authorization`. Também não existe enforcement do endereço de bind.

**Impacto:** se a API for iniciada em `0.0.0.0`, LAN ou rede Docker, todos os
dados ficam acessíveis sem autenticação. A configuração transmite falsa sensação
de segurança.

**Correção recomendada:** implementar dependência global de autenticação para
`/api/v1/*`, comparar tokens em tempo constante e definir explicitamente quais
health checks são públicos. A inicialização deve falhar quando o bind não for
loopback e o token estiver vazio.

### PW-03 — Contrato permite vazamento de labels e metadados sensíveis

**Localização:** `apps/backend/src/portwatch_backend/core/schemas.py:41-59`.

**Motivo:** `ContainerSummary` expõe todos os labels; `ContainerDetail` expõe
comando, nomes de variáveis de ambiente e mounts. Labels Docker podem conter
domínios internos, regras de proxy, nomes de middleware e até credenciais em
configurações inadequadas.

**Impacto:** combinado com a ausência de autenticação, pode revelar topologia do
homelab, caminhos do host e informações operacionais sensíveis. Mesmo com auth,
labels irrestritos ampliam o impacto de um token vazado.

**Correção recomendada:** usar allowlist de labels, redigir chaves sensíveis por
padrão e avaliar se mounts devem expor apenas tipo/destino ou dados agregados.
Formalizar e testar a política de redaction.

### PW-04 — Guard aceita sockets Unix arbitrários e falha aberto

**Localização:** `infra/dev/guard.sh:20-40`.

**Motivo:** aceita qualquer `unix:///*`, aceita endpoint vazio, permite elevar o
limite por `PORTWATCH_DEV_MAX_UNLABELED`, considera apenas containers em execução,
aceita até cinco não rotulados e não confirma que o contexto é `default`.

**Impacto:** um socket Unix pode representar um daemon de produção montado ou
encaminhado localmente. A heurística não cumpre a regra de operar exclusivamente
no daemon local padrão.

**Correção recomendada:** exigir contexto `default`, endpoint canônico esperado e
ausência de overrides como `DOCKER_CONTEXT`. Remover ou limitar fortemente o
bypass configurável e validar a identidade do daemon.

### PW-05 — Rotas estáticas apresentam dados fictícios como reais

**Localização:** `apps/backend/src/portwatch_backend/api/system.py:12-24`,
`containers.py:10-39`, `networks.py:9-28` e `health.py:15-18`.

**Motivo:** endpoints públicos retornam versão Docker, containers, redes e estado
`ready` fictícios sem indicar no payload que são mocks.

**Impacto:** uma implantação acidental pode aparentar estar saudável e conectada
ao Docker enquanto apresenta dados fabricados.

**Correção recomendada:** esconder stubs atrás de modo explícito de
desenvolvimento, retornar `503 Not Ready` enquanto dependências/Collector não
estiverem funcionais ou não registrar essas rotas até a implementação real.

### PW-06 — “GET-only” no socket proxy não elimina leitura de segredos Docker

**Localização:** `docs/adr/0003-docker-access-isolation.md:13-27`.

**Motivo:** endpoints GET do Docker, especialmente inspect de containers, podem
retornar valores completos de variáveis de ambiente, labels, mounts e outras
informações sensíveis. Um backend comprometido pode consultar isso mesmo que a
API pública tente redigir dados.

**Impacto:** o proxy reduz capacidade de mutação, mas não garante
confidencialidade nem limita o raio de leitura tanto quanto o ADR sugere.

**Correção recomendada:** documentar o risco residual. Avaliar um adaptador mínimo
que filtre respostas antes de entregá-las ao processo exposto à rede, ou reforçar
auth, isolamento de rede e hardening do backend.

## Medium

### PW-07 — Frontend consulta endpoint inexistente

**Localização:** `apps/web/src/App.tsx:6-9`,
`apps/backend/src/portwatch_backend/api/health.py:10-12` e
`apps/web/vite.config.ts:14-17`.

**Motivo:** o frontend requisita `/api/health`, mas o backend publica `/health`.
O proxy Vite encaminha o caminho sem remover o prefixo.

**Impacto:** a verificação principal da interface retorna 404 apesar do texto
afirmar que frontend e backend estão conectados.

**Correção recomendada:** alinhar a URL e adicionar teste de integração
frontend/API.

### PW-08 — Tratamento RFC 7807 é incompleto e pode falhar

**Localização:** `apps/backend/src/portwatch_backend/app.py:33-40`.

**Motivo:** `HTTPException.detail` pode ser lista, dicionário ou outro objeto,
mas `ProblemDetail.title` exige string. Erros 422 e exceções inesperadas não usam
o mesmo contrato, headers originais não são preservados e `request_id` nunca é
preenchido.

**Impacto:** formato inconsistente; certas exceções podem virar 500 durante o
próprio handler.

**Correção recomendada:** normalizar `detail`, preservar headers, tratar
`RequestValidationError` e erros internos separadamente e gerar request ID em
middleware isolado.

### PW-09 — Parâmetros de portas e configuração não têm limites válidos

**Localização:** `apps/backend/src/portwatch_backend/core/config.py:17-26` e
`apps/backend/src/portwatch_backend/api/ports.py:13-49`.

**Motivo:** portas negativas ou maiores que 65535 são aceitas; `limit` pode ser
negativo ou arbitrariamente alto e é ignorado; intervalo de polling aceita
valores inválidos; `range_start or default` transforma zero silenciosamente no
valor padrão.

**Impacto:** contratos incorretos e risco futuro de consumo excessivo de CPU ou
memória.

**Correção recomendada:** usar bounds Pydantic/FastAPI, limitar tamanho do
intervalo, validar settings no startup e comparar explicitamente com `None`.

### PW-10 — Estado compartilhado planejado não define consistência

**Localização:** `docs/adr/0001-backend-single-process.md:12-16` e
`docs/adr/0002-no-database-v1.md:11-14`.

**Motivo:** o desenho prevê threads/tasks atualizando estado em memória enquanto
handlers leem, mas não define snapshots imutáveis, locks, geração ou atomicidade
entre containers, redes e portas.

**Impacto:** respostas podem misturar ciclos de coleta ou observar estado
parcial. Múltiplos workers Uvicorn teriam estados independentes.

**Correção recomendada:** publicar snapshots imutáveis completos por troca
atômica de referência, com timestamp e geração. Usar lock se houver atualização
incremental e manter worker único enquanto o estado for local.

### PW-11 — Race TOCTOU entre guard e Compose

**Localização:** `Makefile:5-10` e `infra/dev/guard.sh:28-33`.

**Motivo:** o guard valida o contexto em um processo; o Compose roda depois em
outro. O contexto global pode mudar entre as operações.

**Impacto:** a validação pode ocorrer contra o Docker local e a operação seguinte
contra outro daemon.

**Correção recomendada:** resolver um endpoint/contexto permitido uma única vez e
passá-lo explicitamente a ambas as operações.

### PW-12 — Imagem Docker não é imutável

**Localização:** `infra/dev/docker-compose.dev.yml:12`.

**Motivo:** `nginx:alpine` é tag mutável.

**Impacto:** ambiente não reproduzível e risco de mudança inesperada upstream.

**Correção recomendada:** fixar tag específica e digest, com processo controlado
de atualização.

### PW-13 — CORS contradiz garantia declarada

**Localização:** `apps/backend/src/portwatch_backend/core/config.py:32-33`.

**Motivo:** o comentário diz “never `*`”, mas a configuração não rejeita
wildcard.

**Impacto:** erro de configuração pode liberar leitura por qualquer origem.

**Correção recomendada:** rejeitar wildcard fora de modo de desenvolvimento
explicitamente restrito.

## Low

### PW-14 — Documentação de fase estava divergente

**Localização observada:** `README.md:5-7`, em contraste com
`apps/backend/src/portwatch_backend/app.py:1-5`.

**Motivo:** durante a auditoria, o README ainda dizia que não existiam
API/dashboard e que o projeto estava na Fase 1, enquanto a implementação se
identificava como Fase 2.

**Impacto:** onboarding e avaliação de prontidão confusos.

**Correção recomendada:** manter um status único e distinguir scaffold, mock e
funcionalidade real. Reavaliar no estado atual, pois o README foi modificado
concorrentemente.

### PW-15 — Fronteiras de diretório estavam divergentes — resolvido durante a auditoria

**Localização observada:** versão anterior de `AGENTS.md:40-42` e
`CLAUDE.md:40-42`.

**Motivo:** as regras apontavam para `apps/api` e `apps/collector`, mas código e
ADR-0001 usam `apps/backend`.

**Impacto:** agentes poderiam criar estruturas duplicadas.

**Estado atual:** `CLAUDE.md` agora aponta corretamente para `apps/backend`; o
novo `AGENTS.md` funciona apenas como ponteiro para o documento canônico.

### PW-16 — Ambiente Python local não é reutilizável

**Localização:** `apps/backend/.venv/pyvenv.cfg` (ignorado pelo Git).

**Motivo:** o virtualenv observado apontava para Python montado em
`/tmp/.mount_*`, já inexistente.

**Impacto:** pytest e mypy falham antes da coleta.

**Correção recomendada:** recriar `.venv` com `uv sync` usando instalação Python
estável; não versionar o ambiente virtual.

### PW-17 — Workflow CI usa ações por tags móveis

**Localização:** `.github/workflows/ci.yml:16-35`.

**Motivo:** `actions/checkout@v4`, `setup-uv@v4` e `setup-node@v4` não estão
fixados por SHA.

**Impacto:** risco de supply chain e menor reprodutibilidade, embora reduzido
enquanto o repositório for apenas local.

**Correção recomendada:** quando o CI for usado, fixar ações por commit SHA e
adotar atualização automatizada controlada.

## Sugestões arquiteturais

### S-01 — Separar liveness de readiness

Readiness deve depender de snapshot válido e recente do Collector, conexão com o
socket proxy e, quando habilitado, netprobe. Liveness deve indicar apenas que o
processo/event loop está funcional.

### S-02 — Formalizar modelo de ameaça

Documentar backend comprometido, leitura de secrets via Docker inspect, token
bearer vazado, netprobe comprometido, exposição em LAN e riscos do grupo Docker
no ambiente de desenvolvimento.

### S-03 — Criar contrato OpenAPI versionado

Os schemas Python são chamados de fonte de verdade, mas não há spec exportada nem
tipos frontend gerados. Uma spec versionada detectaria divergências como
`/api/health` versus `/health` e padronizaria problem details.

### S-04 — Definir orçamento de coleta e backpressure

Antes do Collector, documentar timeouts, limite de concorrência, tratamento de
ciclos sobrepostos, política de skip/queue, manutenção do snapshot anterior em
falhas, indicador de dados stale e cancelamento no shutdown.

## Avaliação dos testes

Cobertura observada: quatro testes backend em
`apps/backend/tests/test_health.py`.

### Pontos positivos

- Teste de liveness.
- Teste básico do contrato de summary.
- Verificação de `application/problem+json` para 404.
- Lint, formatação e type-check do frontend passaram.

### Lacunas importantes

- autenticação e bind seguro;
- readiness com dependências indisponíveis;
- validação de faixas e limites;
- erros 422, 500 e `HTTPException.detail` não textual;
- CORS;
- filtros de containers;
- redaction de labels/env/mounts;
- integração frontend/backend;
- guard com contextos e variáveis maliciosas;
- concorrência e consistência do snapshot;
- shutdown do futuro Collector;
- políticas de hardening do Compose.

### Resultado das verificações

| Verificação | Resultado |
|---|---|
| Ruff | Passou |
| ESLint | Passou |
| Prettier check | Passou |
| TypeScript type-check | Passou |
| Docker Compose config | Passou |
| Pytest | Não iniciou: `.venv` inválido |
| mypy | Não iniciou: `.venv` inválido |
| Blueprint externo | Inacessível na sessão |

## Conclusão

Não foi encontrada evidência de endpoints que iniciem, parem, reiniciem ou
executem comandos em containers. O Compose observado também não montava o socket
Docker nem usava `network_mode: host`; nessa fase, o isolamento declarado ainda
não havia sido violado pela implementação.

Os controles contra operação no daemon errado, contudo, não eram suficientemente
fortes. A ausência do guard em `dev-down` é o problema mais urgente, seguida pela
ausência de autenticação e pelo risco de exposição de metadados sensíveis.
