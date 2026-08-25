# ADR-0006 — Autenticação do WebSocket: token na primeira mensagem, não na URL

## Status
Aceito.

## Contexto
`/api/v1/events` (ADR implícita em `66859de`/`eac6174`, ver `api/events.py`)
hoje valida o mesmo bearer token estático (ADR-0004) lido do header
`Authorization` da requisição de upgrade. Isso funciona para qualquer
cliente que controle os headers do handshake, mas a WebSocket API nativa do
browser (`new WebSocket(url)`) não permite setar headers customizados — por
isso o frontend (`apps/web`) ainda não consome o WebSocket e o dashboard
segue em poll via TanStack Query.

Alternativas consideradas para destravar o consumo a partir do browser:
1. **Token via query string** (`?token=...`). Simples de implementar dos
   dois lados, mas o token passa a aparecer em logs de acesso, histórico do
   browser e, se o PortWatch algum dia rodar atrás de um proxy reverso
   (Tailscale Funnel, nginx etc.), em logs desse proxy também — mesmo sendo
   um único token estático de homelab, é um vazamento gratuito e evitável.
2. **`Sec-WebSocket-Protocol` como veículo do token.** Evita a URL, mas é um
   uso não-idiomático do subprotocolo negociado e mais confuso de debugar.
3. **Token como primeira mensagem do socket**, enviada pelo cliente
   imediatamente após `onopen`, antes de qualquer evento ser publicado.

## Decisão
Opção 3. O servidor aceita a conexão (`websocket.accept()`), mas não inicia
o fan-out de eventos até receber uma primeira mensagem de texto no formato
`{"token": "<bearer>"}` dentro de uma janela curta (5s). Token inválido ou
ausente dentro da janela → `websocket.close(code=1008)`, mesmo código já
usado hoje para o caso de header ausente/inválido. O endpoint deixa de exigir
o header `Authorization` no handshake (continua aceitando-o como fallback
para clientes não-browser que já o enviam, ex.: os testes ASGI diretos e um
futuro cliente CLI/script) — a primeira mensagem é o caminho obrigatório
quando o header não veio.

`validate_api_token()` (`core/auth.py`) já é independente da extração
HTTP/header e é reaproveitada como está para validar o token vindo da
mensagem.

## Consequências
- O token nunca aparece em URL, querystring ou log de proxy — só trafega
  dentro do payload já criptografado da conexão WS (mesma superfície de
  exposição que o header `Authorization` tinha).
- Cliente browser: abrir o socket, mandar `{"token": "..."}` como primeira
  mensagem, só então tratar mensagens subsequentes como eventos
  `snapshot.updated`.
- Pequeno custo: um round-trip extra (accept → primeira mensagem) antes do
  primeiro evento poder ser entregue; irrelevante para o caso de uso
  (dashboard local).
- Testes de `tests/test_events.py` cobrindo o path de header (já existentes)
  continuam válidos como fallback; precisam de testes novos para o path de
  primeira mensagem (sucesso, token errado, timeout sem mensagem).
