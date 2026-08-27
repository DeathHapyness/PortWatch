# Documentação do PortWatch

- [`adr/`](./adr/) — decisões arquiteturais aceitas.
- [`reference/configuration.md`](./reference/configuration.md) — toda variável
  de ambiente do backend, netprobe e frontend, com defaults e limites.
- [`security/threat-model.md`](./security/threat-model.md) — ativos, fronteiras
  de confiança, ameaças e riscos residuais.
- [`security/operator-guide.md`](./security/operator-guide.md) — requisitos
  mínimos para uma implantação segura.
- [`release/public-release-checklist.md`](./release/public-release-checklist.md)
  — critérios verificáveis para publicar uma versão utilizável.
- [`audits/`](./audits/) — auditorias históricas; um achado antigo pode já ter
  sido corrigido e deve ser conferido contra o código atual.
- [`../infra/prod/`](../infra/prod/) — Compose de produção (backend +
  frontend + docker-socket-proxy, non-root, `read_only`, sem TLS embutido).

As regras permanentes para desenvolvimento e agentes continuam em
[`../CLAUDE.md`](../CLAUDE.md).
