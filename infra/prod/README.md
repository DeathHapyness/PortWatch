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
cd infra/prod
export PORTWATCH_API_TOKEN="$(openssl rand -hex 32)"
export PORTWATCH_CORS_ALLOW_ORIGINS='["https://portwatch.exemplo.com"]'
docker compose -f docker-compose.prod.yml up -d --build
curl http://127.0.0.1:8080/health
```

Sem essas duas variáveis definidas, o `up` falha cedo com uma mensagem
explicando qual falta — não existe fallback silencioso para "sem token" ou
"sem CORS restrito" aqui (ao contrário do backend sozinho em dev, que aceita
ambos vazios em loopback).

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
