# Checklist de release público

Nenhuma versão deve ser anunciada como pronta para usuários enquanto os itens
**bloqueadores** estiverem abertos.

## Bloqueadores

- [x] Licença MIT e arquivos comunitários integrados na `main`.
- [x] Token do frontend informado em runtime, sem segredo no bundle.
- [x] Dockerfiles de produção para backend e frontend —
      `apps/backend/Dockerfile`, `apps/web/Dockerfile` (nginx-unprivileged
      + proxy para `/api/`, incl. upgrade de WebSocket).
- [x] Compose de produção separado do sandbox de desenvolvimento —
      `infra/prod/docker-compose.prod.yml`, ver `infra/prod/README.md`.
- [x] Imagens non-root, com healthcheck e limites documentados — os três
      serviços do compose de produção rodam non-root, `read_only`,
      `cap_drop: ALL`, `no-new-privileges`, com CPU/memória/PIDs definidos.
      Coberto pelo job `prod-images` do CI (build real das duas imagens +
      `up` do compose + healthcheck).
- [x] Socket Docker montado exclusivamente no proxy GET-only — único mount
      em todo `infra/prod/docker-compose.prod.yml`; backend e frontend não
      publicam porta no host. Verificado por `docker port` tanto
      manualmente quanto no job `prod-images` do CI (falha o job se algo
      além do frontend publicar uma porta).
- [ ] Quickstart validado do zero em um host Linux limpo. (o job
      `prod-images` do CI cobre isso em um runner efêmero a cada push/PR —
      build+up+smoke test completo da cadeia
      frontend→backend→docker-socket-proxy→Docker real, incl. checagem de
      que o `Server` header não vaza; falta apenas alguém validar o mesmo
      passo a passo manualmente em um host de operador real, fora de CI)
- [x] Referência de todas as variáveis de ambiente, defaults e limites —
      `docs/reference/configuration.md`.
- [ ] TLS/reverse proxy e rotação do token documentados.
- [ ] Suíte backend, frontend, Netprobe, políticas de Compose e E2E verdes.
- [x] Teste real confirma que Uvicorn/proxy não divulga versão no `Server`
      (verificado manualmente 2026-08-26 — build+run real da imagem +
      `curl` — e automatizado desde 2026-08-27 no job `prod-images` do CI,
      que falha se o header voltar a aparecer).
- [ ] Scan de dependências, secrets e imagens sem achado bloqueador.
- [ ] Branch protection e revisão obrigatória habilitadas.
- [ ] Private Vulnerability Reporting e alertas do Dependabot habilitados.

## Artefatos da versão

- [ ] Versões do backend/frontend e tag Git são coerentes.
- [ ] `CHANGELOG.md` descreve recursos, correções, segurança e breaking changes.
- [ ] Imagens multi-arquitetura ou arquiteturas suportadas explicitamente listadas.
- [ ] Imagens publicadas por versão e SHA; `latest` não é a única referência.
- [ ] Digests, SBOM e attestations de proveniência publicados.
- [ ] Release notes incluem instalação, upgrade, rollback e limitações conhecidas.

## Validação de uso

- [ ] Instalação não requer clonar código nem instalar Node/Python no host.
- [ ] Primeiro snapshot aparece e o dashboard atualiza por WebSocket.
- [ ] Polling mantém o dashboard utilizável após queda do WebSocket.
- [ ] Containers, redes, portas publicadas e portas do host batem com fixtures.
- [ ] Token ausente/incorreto produz erro compreensível no dashboard.
- [ ] Reinício não cria estado incoerente nem exige limpeza manual.
- [ ] Desinstalação não remove containers/volumes que não sejam do PortWatch.

## Depois da publicação

- [ ] Monitorar CI, advisories e falhas de instalação reportadas.
- [ ] Definir prazo de suporte e política para versões anteriores.
- [ ] Ensaiar atualização e correção emergencial de uma imagem publicada.
- [ ] Revisar este checklist e o modelo de ameaça a cada release menor.
