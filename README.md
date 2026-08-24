# PortWatch

Plataforma de monitoramento de homelab — Docker, containers e portas de rede.

Status atual: **Fase 1 — Development Environment**. Ainda não há aplicação
(API/dashboard); esta fase entrega apenas o ferramental e o sandbox de
desenvolvimento. Arquitetura completa e roadmap:
https://claude.ai/code/artifact/b41be8c8-2963-4ef8-a4f7-b984b68407a8

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
