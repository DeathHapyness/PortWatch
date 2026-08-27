# Compose de produção

`docker-compose.prod.yml` sobe o PortWatch containerizado: `docker-socket-proxy`
(GET-only, único mount do socket real, sem porta publicada), `backend`
(construído de `apps/backend/Dockerfile`, sem porta publicada) e `frontend`
(construído de `apps/web/Dockerfile`, único serviço publicado, em
`127.0.0.1:8087`). Todos os três rodam non-root, `read_only`, `cap_drop: ALL`,
`no-new-privileges` e com limites de CPU/memória/PIDs — ver comentários no
próprio compose para o porquê de cada escolha.

**Netprobe (portas ocupadas do host) não está incluído.** Não é uma omissão:
Netprobe só aceita bind em loopback e é o único componente autorizado a usar
`network_mode: host` (ver `CLAUDE.md`) — um backend containerizado nesta
topologia está em um namespace de rede diferente do host e não alcança um
Netprobe em loopback por construção. Se você precisa de visibilidade de
portas do host, rode o backend nativamente ao lado do Netprobe (mesmo padrão
do sandbox de desenvolvimento, ver `docs/README.md`) em vez deste compose.

## Uso

```sh
git clone <este repositório>
cd PortWatch/infra/prod
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs backend | grep PORTWATCH_API_TOKEN=
```

Deu algum erro, ou o `docker compose ps` não mostra o que você esperava?
Ver ["Problemas comuns"](#problemas-comuns) no fim deste documento antes de
mais nada — cobre os dois erros mais prováveis (porta já em uso, e não
conseguir acessar de outra máquina) passo a passo.

Sem clonar mais nada além disso, sem instalar Node/Python/uv localmente, e
sem precisar gerar nada à mão antes: se `PORTWATCH_API_TOKEN` não for
definido, `apps/backend/docker-entrypoint.sh` gera um token aleatório na
hora e imprime nos logs do container — cole-o no dashboard
(`http://127.0.0.1:8087`, ícone de chave no header) e pronto. Esse token
não é persistido (muda a cada `docker compose restart`/`up` sem
`PORTWATCH_API_TOKEN` definido) — para um valor estável entre reinícios,
defina a variável você mesmo antes do `up`:

```sh
export PORTWATCH_API_TOKEN="$(openssl rand -hex 32)"
```

`PORTWATCH_CORS_ALLOW_ORIGINS` já vem com o default correto
(`127.0.0.1:8087` e `localhost:8087` — os navegadores tratam os dois como
origens diferentes mesmo sendo o mesmo lugar) para a topologia padrão deste
compose — só precisa ser definido se você também mudar a porta/host
publicado do frontend (ex. atrás de um domínio real, ver seção abaixo).

Validado manualmente nesta máquina (build + up + smoke test completo:
estático, proxy de API sem/com token, a cadeia real
frontend → backend → docker-socket-proxy → Docker local, e ausência do
header `Server` no backend) em 2026-08-27, e automatizado desde então no job
`prod-images` do CI (`.github/workflows/ci.yml`) a cada push/PR — falta
apenas alguém repetir o mesmo passo a passo manualmente em um host de
operador real (fora de um runner efêmero de CI).

## Acessar de outra máquina (IP do seu server, não localhost)

O default publica só em `127.0.0.1:8087` — só alcançável de dentro do
próprio host. Se o seu navegador está em outra máquina (o caso comum de
"testar no meu server": você acessa o dashboard do seu notebook, não do
console do server), defina onde publicar e ajuste o CORS para bater com a
URL que você vai realmente usar no navegador:

```sh
export PORTWATCH_FRONTEND_PUBLISH=192.168.1.50:8087   # o IP real do seu server
export PORTWATCH_CORS_ALLOW_ORIGINS='["http://192.168.1.50:8087"]'
docker compose -f docker-compose.prod.yml up -d --build
```

As duas variáveis precisam bater: `PORTWATCH_FRONTEND_PUBLISH` é onde o
Docker escuta; `PORTWATCH_CORS_ALLOW_ORIGINS` é a URL que o navegador vai
usar para chamar a API — se divergirem, a página carrega mas toda chamada
de API falha por CORS sem erro óbvio. Verificado manualmente nesta máquina
com um IP de LAN de verdade (não loopback): dashboard, CORS e autenticação
funcionando através dele.

Isso já conta como "exposição na rede", não mais loopback: o token
auto-gerado por `docker-entrypoint.sh` continua funcionando tecnicamente,
mas não foi pensado pra isso — defina `PORTWATCH_API_TOKEN` você mesmo (ver
seção acima) antes de deixar rodando assim por mais que um teste rápido, e
veja
[`../../docs/security/operator-guide.md`](../../docs/security/operator-guide.md)
para TLS/reverse proxy e o restante dos requisitos mínimos antes de expor
para além da sua própria LAN de confiança.

## Problemas comuns

### `Bind for 0.0.0.0:8087 failed: port is already allocated`

A porta escolhida (8087 por padrão) já está em uso por outra coisa no seu
host — bem comum em homelab (Portainer, outro dashboard, um proxy que já
existe). Descubra o que é:

```sh
sudo ss -tlnp | grep :8087
# ou
docker ps -a --filter publish=8087
```

Se não for algo que você queira derrubar, troque a porta:

```sh
export PORTWATCH_FRONTEND_PUBLISH=127.0.0.1:8090   # qualquer porta livre
export PORTWATCH_CORS_ALLOW_ORIGINS='["http://127.0.0.1:8090", "http://localhost:8090"]'
docker compose -f docker-compose.prod.yml up -d --build
```

### Defini `PORTWATCH_FRONTEND_PUBLISH`, mas `docker compose ps` ainda mostra `127.0.0.1:8087`

De longe o erro mais comum ao tentar acessar de outra máquina. Duas causas
possíveis, as duas com a mesma raiz — as variáveis `export`adas não
chegaram até o `docker compose up`:

1. **`export` e `up` em sessões de shell diferentes.** Se você exportou a
   variável, depois abriu outra aba do terminal, reconectou o SSH, ou rodou
   os comandos em blocos separados, o valor exportado se perde — `export`
   só vale pro processo do shell atual e seus filhos diretos. Rode tudo de
   uma vez, sem trocar de sessão no meio:

   ```sh
   docker compose down
   export PORTWATCH_FRONTEND_PUBLISH=<SEU_IP>:8087
   export PORTWATCH_CORS_ALLOW_ORIGINS='["http://<SEU_IP>:8087"]'
   docker compose up -d --build
   docker compose ps   # PORTS deve mostrar <SEU_IP>:8087, não 127.0.0.1:8087
   ```

2. **`docker compose up` sem `down` antes, num container que já existia.**
   O Compose normalmente recria um serviço sozinho quando a config muda,
   mas se algo ficou num estado estranho de uma tentativa anterior, um
   `docker compose down` limpo antes do `up` elimina qualquer dúvida.

### Qual IP eu uso no `PORTWATCH_FRONTEND_PUBLISH`?

Em uma máquina com Docker (e principalmente com Kubernetes/k3s, que cria
dezenas de interfaces de rede virtuais), `hostname -I` pode devolver uma
lista enorme de IPs — a maioria deles é rede interna de containers/pods,
não o IP real da sua LAN. Para achar o IP correto:

```sh
ip route get 1.1.1.1
```

A interface/IP que aparece aí (`src ...`) é o que sua máquina usa de
verdade pra sair pra internet/rede local — normalmente é esse o IP certo,
não os que terminam em `.0.1`/`.1` isolados em dezenas de faixas diferentes
(esses costumam ser gateways de redes virtuais Docker/bridge/k3s, um por
rede, não o host em si).

### Containers ficam em `Up (health: starting)` e não conecta

Espera uns 15–30s — o healthcheck do backend só fica `healthy` depois do
primeiro ciclo do Collector. Roda `docker compose ps` de novo até `backend`
e `frontend` aparecerem como `(healthy)`.

### Ainda não conecta depois de tudo isso

```sh
docker compose ps                     # PORTS bate com IP/porta esperados?
docker compose logs backend           # erro real no backend?
docker compose logs frontend          # erro real no nginx?
curl http://<SEU_IP>:8087/            # rodado NO PRÓPRIO SERVER
```

Se o `curl` acima (rodado no próprio server, contra o IP público dele, não
`127.0.0.1`) já falhar, o problema não é a rede até a sua máquina — é o
container mesmo, e os logs acima vão dizer o quê.
