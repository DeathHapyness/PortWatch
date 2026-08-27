# Compose de produção

`docker-compose.prod.yml` sobe o PortWatch containerizado: `docker-socket-proxy`
(GET-only, único mount do socket real, sem porta publicada), `backend`
(construído de `apps/backend/Dockerfile`, sem porta publicada) e `frontend`
(construído de `apps/web/Dockerfile`, único serviço publicado, em
`127.0.0.1:8080`). Todos os três rodam non-root, `read_only`, `cap_drop: ALL`,
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

Sem clonar mais nada além disso, sem instalar Node/Python/uv localmente, e
sem precisar gerar nada à mão antes: se `PORTWATCH_API_TOKEN` não for
definido, `apps/backend/docker-entrypoint.sh` gera um token aleatório na
hora e imprime nos logs do container — cole-o no dashboard
(`http://127.0.0.1:8080`, ícone de chave no header) e pronto. Esse token
não é persistido (muda a cada `docker compose restart`/`up` sem
`PORTWATCH_API_TOKEN` definido) — para um valor estável entre reinícios,
defina a variável você mesmo antes do `up`:

```sh
export PORTWATCH_API_TOKEN="$(openssl rand -hex 32)"
```

`PORTWATCH_CORS_ALLOW_ORIGINS` já vem com o default correto
(`["http://127.0.0.1:8080"]`) para a topologia padrão deste compose — só
precisa ser definido se você também mudar a porta/host publicado do
frontend (ex. atrás de um domínio real, ver seção abaixo).

Validado manualmente nesta máquina (build + up + smoke test completo:
estático, proxy de API sem/com token, a cadeia real
frontend → backend → docker-socket-proxy → Docker local, e ausência do
header `Server` no backend) em 2026-08-27, e automatizado desde então no job
`prod-images` do CI (`.github/workflows/ci.yml`) a cada push/PR — falta
apenas alguém repetir o mesmo passo a passo manualmente em um host de
operador real (fora de um runner efêmero de CI).

## Antes de expor fora de loopback

Este compose não inclui TLS. Ver
[`../../docs/security/operator-guide.md`](../../docs/security/operator-guide.md)
para reverse proxy, rotação de token e o restante dos requisitos mínimos
antes de publicar a porta 8080 em qualquer coisa além de `127.0.0.1`.
