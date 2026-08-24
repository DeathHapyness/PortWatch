# PortWatch

Plataforma de monitoramento de homelab: descoberta de containers Docker, status,
portas publicadas, portas ocupadas/disponíveis no host e redes Docker. API +
dashboard web. Ver o blueprint de arquitetura completo (aprovado) em:
https://claude.ai/code/artifact/b41be8c8-2963-4ef8-a4f7-b984b68407a8

Este arquivo carrega regras permanentes para qualquer agente (humano ou Claude)
trabalhando neste repositório. Decisões arquiteturais detalhadas ficam em `docs/`
conforme forem sendo produzidas (a partir da Fase 2).

## Regras permanentes de segurança e escopo

- **Nenhum agente tem autorização para acessar ou alterar o homelab de produção
  do usuário.** Todo desenvolvimento, teste e execução de containers acontece
  exclusivamente no Docker local desta máquina de desenvolvimento
  (`docker context` = `default`, `unix:///var/run/docker.sock` local).
- O único ambiente Docker onde é permitido criar/destruir containers é o
  sandbox de dev em `infra/dev/docker-compose.dev.yml`. Nunca aponte
  `DOCKER_HOST`/contexto para outro host.
- Containers de teste/fixture devem carregar o label `portwatch.env=dev-sandbox`.
  `infra/dev/guard.sh` verifica isso antes de subir a stack — não contorne o guard.
- PortWatch em si é **somente-observação** na v1: nenhum endpoint da API inicia,
  para, reinicia ou executa comando em containers monitorados.
- Acesso ao socket Docker real é exclusivo do `docker-socket-proxy`
  (GET-only). A aplicação nunca monta `/var/run/docker.sock` diretamente.
- `network_mode: host` é exclusivo do componente `netprobe`, que não tem acesso
  ao socket Docker. Nenhum outro componente recebe esse modo de rede.
- Autenticação da v1 é um token estático simples — não implemente contas de
  usuário, OAuth ou fluxos de auth mais complexos sem decisão explícita do QA.
- Antes de qualquer operação que altere configuração global do host (fora deste
  repositório/diretório do usuário) ou exija privilégios elevados (sudo),
  pare e peça autorização.

## Agentes

Principais (ativos ao longo do projeto): **Lead**, **Backend**, **Frontend**, **DevOps**.
Especializados, sob demanda (não permanentes): **Architect**, **Security**.

- Cada agente trabalha em worktree/branch próprio (`agent/<área>/<tarefa>`).
- Fronteiras por diretório: Backend → `apps/api`, `apps/collector`;
  Frontend → `apps/web`; DevOps → `infra/`, `.github/`.
- Arquivos de contrato compartilhado (spec OpenAPI, tipos gerados) só são
  editados por Architect/Lead.
- Nenhum agente faz merge do próprio trabalho — todo PR passa por revisão do Lead.

## Stack aprovada

Backend: Python 3.12, FastAPI, Pydantic v2, `uv`.
Frontend: React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query, Recharts.
Estado no frontend: nativo do React por padrão; Zustand só se surgir necessidade
concreta (evitar adicionar por precaução).
Observabilidade: logs estruturados + métricas Prometheus no MVP; OpenTelemetry
fica fora do MVP, mas a integração não deve ser bloqueada — deixe pontos de
extensão óbvios (ex.: middleware de request isolado) em vez de acoplar tudo.
Persistência: nenhuma no MVP (estado é derivado ao vivo do Docker/host).

## Git

`main` é protegida — sem commit direto. Conventional Commits
(`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Repositório **local apenas**;
não criar/configurar remoto (GitHub ou outro) sem autorização explícita do QA.
