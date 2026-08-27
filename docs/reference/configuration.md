# Referência de configuração

Todas as variáveis de ambiente lidas pelo backend, pelo netprobe e pelo
frontend, com defaults, limites validados e o que acontece fora deles. Gerado
a partir do código-fonte atual (`core/config.py`, `infra/netprobe/netprobe.py`,
`lib/config.ts`) — em caso de dúvida, essas são as fontes de verdade.

## Backend (`apps/backend`)

Prefixo `PORTWATCH_`. Lidas uma vez no startup via `Settings`
(`core/config.py`); um valor inválido derruba o processo imediatamente com
uma mensagem de erro explicando qual variável e por quê — nunca falha
silenciosamente para um default.

| Variável | Default | Limite/validação |
|---|---|---|
| `PORTWATCH_ENVIRONMENT` | `development` | livre, apenas identificação |
| `PORTWATCH_LOG_LEVEL` | `INFO` | `CRITICAL`\|`ERROR`\|`WARNING`\|`INFO`\|`DEBUG` (case-insensitive) |
| `PORTWATCH_BIND_HOST` | `127.0.0.1` | declaração do bind real do processo — **precisa ficar em sincronia com o `--host` de verdade do uvicorn**; não loopback + token vazio recusa iniciar (ver abaixo) |
| `PORTWATCH_API_TOKEN` | `` (vazio) | vazio = sem autenticação (só aceito em loopback); não pode ser só espaços em branco. Na imagem de produção do backend (`apps/backend/Dockerfile`), `PORTWATCH_BIND_HOST` nunca é loopback, então vazio aqui faz `docker-entrypoint.sh` gerar um token aleatório na hora (impresso nos logs do container) em vez de recusar iniciar — ver `infra/prod/README.md`. |
| `PORTWATCH_CORS_ALLOW_ORIGINS` | `["http://localhost:5173"]` | lista de origens exatas como **array JSON** (não string separada por vírgula — ex. `["https://portwatch.exemplo.com"]`); `*` é rejeitado |
| `PORTWATCH_DOCKER_PROXY_URL` | `http://docker-socket-proxy:2375` | URL http(s) absoluta, sem espaço, sem credenciais embutidas |
| `PORTWATCH_NETPROBE_URL` | `null` (desabilitado) | mesma validação de URL acima; `null`/ausente desliga a leitura de portas do host |
| `PORTWATCH_PORT_RANGE_START` | `1024` | `0`–`65535` |
| `PORTWATCH_PORT_RANGE_END` | `65535` | `0`–`65535`; precisa ser `>= PORT_RANGE_START` |
| `PORTWATCH_COLLECTOR_POLL_INTERVAL_SECONDS` | `30.0` | finito e `> 0` |
| `PORTWATCH_COLLECTOR_CYCLE_BUDGET_SECONDS` | `25.0` | finito e `> 0` — ver ADR-0007 |
| `PORTWATCH_COLLECTOR_MAX_CONTAINERS` | `1000` | `1`–`100000` — ver ADR-0007 |
| `PORTWATCH_COLLECTOR_MAX_NETWORKS` | `1000` | `1`–`100000` — ver ADR-0007 |
| `PORTWATCH_WEBSOCKET_MAX_SUBSCRIBERS` | `128` | `1`–`10000` — conexões acima do limite recebem WS 1013 |

Também aceita um arquivo `.env` na raiz de `apps/backend` (mesmas chaves,
`SettingsConfigDict(env_file=".env")`); variáveis de ambiente reais têm
prioridade sobre o arquivo. Chaves desconhecidas são ignoradas (`extra="ignore"`).

**`PORTWATCH_BIND_HOST` vs. `--host` do uvicorn:** são duas coisas diferentes
que precisam contar a mesma história. `--host` é o que o uvicorn realmente
faz; `PORTWATCH_BIND_HOST` é a declaração que o app usa para decidir se pode
rodar sem token. Se divergirem (ex.: uvicorn em `0.0.0.0` mas
`PORTWATCH_BIND_HOST` no default `127.0.0.1`), a checagem de segurança fica
cega para uma exposição real — ver `apps/backend/Dockerfile` para o exemplo
correto (ambos setados para `0.0.0.0` juntos).

## Netprobe (`infra/netprobe`)

Sem prefixo — processo independente, próprio `main()`.

| Variável | Default | Limite/validação |
|---|---|---|
| `NETPROBE_HOST` | `127.0.0.1` | precisa ser um IP de loopback (`127.0.0.0/8` ou `::1`) — qualquer outro valor recusa iniciar |
| `NETPROBE_PORT` | `8088` | `1024`–`65535` |

## Frontend (`apps/web`, build-time)

Prefixo `VITE_` (convenção do Vite — só essas variáveis chegam ao bundle).

| Variável | Default | Observação |
|---|---|---|
| `VITE_API_TOKEN` | `` (vazio) | **fallback de conveniência para dev local apenas.** Fica em texto puro no bundle JS de produção (comportamento padrão do Vite) — nunca use isso para um deploy fora de loopback. O caminho recomendado é digitar o token em runtime pelo ícone de chave no header do dashboard (`ApiTokenDialog`), que grava só em `localStorage` daquele navegador. |

## Ver também

- [`../security/operator-guide.md`](../security/operator-guide.md) — como
  combinar essas variáveis para uma implantação segura fora de loopback.
- [`../security/threat-model.md`](../security/threat-model.md) — por que cada
  limite existe.
- `apps/backend/src/portwatch_backend/core/config.py` — implementação e
  mensagens de erro exatas.
