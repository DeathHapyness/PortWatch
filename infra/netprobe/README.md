# netprobe

Utilitário mínimo, de propósito único: expõe as portas TCP/UDP ocupadas no
host de desenvolvimento como JSON, lendo diretamente `/proc/net/tcp`,
`/proc/net/tcp6`, `/proc/net/udp` e `/proc/net/udp6` (sem shell out para
`ss`/`netstat`, sem dependências além da stdlib do Python).

Existe porque essa visibilidade só é possível a partir da netns do host —
por isso é o único componente do PortWatch que roda com
`network_mode: host` (ver `docs/adr/0003-docker-access-isolation.md`). Em
troca, não tem nenhum acesso ao socket Docker nem a qualquer outra
capability além do estritamente necessário para ler esses arquivos e abrir
um socket de escuta em loopback.

Não segue a stack "aprovada" do backend (FastAPI/Pydantic) — é
deliberadamente pequeno o bastante para ser lido e auditado em poucos
minutos, então stdlib (`http.server`) é suficiente e reduz superfície.

## Contrato HTTP

### `GET /host-ports`

Retorna as portas ocupadas no host no momento da chamada.

- TCP: apenas sockets em estado `LISTEN` (é o que importa para decidir se
  uma porta está livre para um novo serviço escutar; conexões estabelecidas
  reaproveitam a porta de um listener já contado, ou são portas efêmeras de
  saída, irrelevantes aqui).
- UDP: qualquer socket vinculado (UDP não tem estado de "listen"; qualquer
  entrada na tabela representa uma porta em uso).

Exemplo de resposta:

```json
{
  "generated_at": "2026-08-23T14:02:11Z",
  "count": 3,
  "ports": [
    {"protocol": "tcp", "family": "ipv4", "address": "0.0.0.0", "port": 22},
    {"protocol": "tcp", "family": "ipv4", "address": "127.0.0.1", "port": 5173},
    {"protocol": "udp", "family": "ipv6", "address": "::", "port": 68}
  ],
  "tcp_listen_ports": [22, 5173],
  "udp_ports": [68]
}
```

Campos:

| Campo | Tipo | Descrição |
|---|---|---|
| `generated_at` | string (UTC, `%Y-%m-%dT%H:%M:%SZ`) | Momento da leitura — cada chamada relê `/proc/net/*` ao vivo, não há cache. |
| `count` | int | Número de entradas em `ports`. |
| `ports` | array | Uma entrada por combinação única de `(protocol, address, port)`. |
| `ports[].protocol` | `"tcp"` \| `"udp"` | |
| `ports[].family` | `"ipv4"` \| `"ipv6"` | |
| `ports[].address` | string | Endereço local vinculado (`0.0.0.0`/`::` = todas as interfaces). |
| `ports[].port` | int | Porta local (0–65535). |
| `tcp_listen_ports` | array de int, ordenada, sem duplicatas | Atalho para quem só quer números de porta TCP. |
| `udp_ports` | array de int, ordenada, sem duplicatas | Atalho equivalente para UDP. |

Sem PID/nome de processo no payload de propósito — mapear porta→processo
exigiria correlacionar o `inode` da tabela com `/proc/*/fd`, o que aumenta
complexidade e normalmente exige rodar como root ou com `CAP_SYS_PTRACE`;
fora do escopo mínimo deste utilitário.

### `GET /health`

Liveness simples: `{"status": "ok"}` com HTTP 200 se o processo está de pé.
Não depende de nenhum recurso externo.

### Qualquer outra rota/método

`404 {"error": "not found"}`. Não há outros verbos implementados (é
read-only por natureza — nenhuma rota de escrita existe).

## Hardening aplicado e por quê

Testado manualmente contra o sandbox de dev (`docker compose run` avulso,
depois validado dentro do `docker-dev-compose.dev.yml`):

| Controle | Valor | Por quê funciona aqui |
|---|---|---|
| Usuário | não-root (`netprobe`, uid 10001) | Leitura de `/proc/net/*` é permitida a qualquer usuário (arquivos world-readable no namespace de rede do processo); a porta de escuta (8088, > 1024) não exige `CAP_NET_BIND_SERVICE`. Nenhuma operação do processo exige root. |
| `read_only: true` (filesystem raiz) | sim | O processo só lê arquivos (`netprobe.py`, `/proc/net/*`) e escreve na rede — não escreve em disco. Nenhum tmpfs adicional foi necessário. |
| `cap_drop: [ALL]` | sim, nenhuma capability devolvida | Confirmado por teste: com todas as capabilities derrubadas, `GET /host-ports` continua respondendo com dados reais. Não há `cap_add`. |
| `security_opt: no-new-privileges:true` | sim | Sem binários setuid envolvidos; não há motivo para escalar privilégio em tempo de execução. |
| `network_mode: host` | sim (único componente autorizado, ver ADR-0003) | É o requisito funcional: sem isso, `/proc/net/*` mostraria apenas a netns isolada do container, não a do host. |
| Bind de rede | IP de loopback, `127.0.0.1:8088` por padrão, validado no startup | Como `network_mode: host` não passa por `ports:` do Compose (o mapeamento de portas não se aplica nesse modo), o próprio processo recusa `NETPROBE_HOST` que não seja um IP de loopback. `NETPROBE_PORT` também é limitado a 1024–65535 para preservar a execução sem capabilities. |
| Acesso ao socket Docker | nenhum | Não montado, não referenciado, não necessário — função única. |

Todas as respostas incluem `Cache-Control: no-store` e
`X-Content-Type-Options: nosniff`. Falhas inesperadas ao ler as tabelas do
kernel retornam `503` sem expor caminhos ou detalhes internos ao cliente. O
cliente do Collector, por sua vez, rejeita respostas maiores que 1 MiB antes
de decodificar o JSON, inclusive quando o servidor omite `Content-Length`.

## Como o backend deve consumir

Durante o desenvolvimento, o backend roda nativamente no host (`uv run
uvicorn`, fora de qualquer rede Docker), então deve apontar para
`http://127.0.0.1:8088` via `PORTWATCH_NETPROBE_URL` (ver
`apps/backend/src/portwatch_backend/core/config.py` e o `README.md` da raiz
do repo). Ausência dessa variável (`None`) deve continuar desabilitando o
recurso de host-ports, como já documentado no config do backend — netprobe
é um recurso opcional, não uma dependência rígida.
