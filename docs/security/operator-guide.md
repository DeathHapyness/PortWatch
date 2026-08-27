# Guia de implantação segura

Este guia define os mínimos de segurança para operadores. Imagens e Compose
de produção já existem (`apps/backend/Dockerfile`, `apps/web/Dockerfile`,
`infra/prod/docker-compose.prod.yml`), mas vários dos itens abaixo (scan de
dependências/imagens, branch protection, quickstart validado do zero) ainda
não estão fechados — ver
[`../release/public-release-checklist.md`](../release/public-release-checklist.md)
para o estado real antes de tratar isto como pronto para exposição fora de
loopback.

## Requisitos do host

- Linux com Docker e Compose mantidos e suportados pelo fornecedor.
- Acesso administrativo limitado; pertencer ao grupo `docker` equivale, na
  prática, a poder controlar o host.
- Firewall ativo e nenhuma porta do socket proxy ou Netprobe exposta à LAN.
- Armazenamento e logs sem credenciais ou dumps não redigidos do Docker.

## Topologia obrigatória

- O socket real só pode ser montado no `docker-socket-proxy` e como read-only.
- O backend fala com o proxy por rede privada e nunca monta o socket.
- O Netprobe é o único componente com `network_mode: host`.
- O Netprobe não recebe socket Docker, volumes do usuário ou capabilities.
- API e dashboard devem ficar em loopback por padrão.

Não copie `infra/dev/docker-compose.dev.yml` para produção: ele contém fixture,
nomes e guard voltados exclusivamente ao sandbox de desenvolvimento. Use
`infra/prod/docker-compose.prod.yml` (ver `infra/prod/README.md`) — ele já
aplica non-root, `read_only`, `cap_drop: ALL` e limites de CPU/memória/PIDs
nos três serviços, e não publica o socket proxy nem o backend fora da rede
interna do compose.

## Exposição na rede

Para acesso fora do próprio host:

1. configure um token longo e aleatório — não use o token que
   `apps/backend/docker-entrypoint.sh` gera sozinho quando
   `PORTWATCH_API_TOKEN` não é definido: ele existe só para "cloná e suba"
   em loopback sem fricção, muda a cada reinício e nunca foi pensado para
   sobreviver a uma exposição real;
2. termine TLS em um reverse proxy mantido;
3. aplique uma camada adicional de acesso, como VPN privada ou autenticação do
   proxy;
4. restrinja CORS à origem exata do dashboard;
5. declare `PORTWATCH_BIND_HOST` coerente com o bind real;
6. não exponha as portas do socket proxy nem do Netprobe.

Um token estático não oferece usuários, revogação individual, expiração ou
auditoria por identidade. Trate-o como uma senha compartilhada e rotacione-o
após qualquer suspeita de vazamento.

## Configuração e segredos

- Não coloque tokens no repositório, imagem, argumento de build ou URL.
- Prefira secret files ou o mecanismo de secrets do ambiente de implantação.
- Não use `VITE_API_TOKEN`: variáveis `VITE_*` são incorporadas ao JavaScript.
- Revise logs antes de compartilhá-los; redação automática é best-effort.
- Defina limites de CPU, memória e PIDs, rootfs read-only, `cap_drop: ALL` e
  `no-new-privileges` sempre que compatível com cada imagem.

## Verificação antes de expor

- `/health` responde sem revelar inventário.
- `/health/ready` só fica pronto após snapshot recente.
- rotas `/api/v1/*` e `/metrics` rejeitam ausência e erro de token.
- REST e WebSocket funcionam com o mesmo token informado em runtime.
- respostas sensíveis usam `Cache-Control: no-store`.
- nenhum serviço interno escuta em `0.0.0.0` sem decisão explícita.
- imagens estão pinadas por versão/digest e passaram por scan.
- backup não é necessário para estado do PortWatch, pois a v1 não persiste
  dados; preserve apenas configuração e segredos pelo mecanismo do operador.

## Incidentes

Em caso de token vazado, remova a exposição externa, gere outro token, reinicie
os componentes consumidores e invalide caches/proxies. Se houver suspeita de
comprometimento do proxy Docker ou do host, a rotação do token não é suficiente:
isole o host e siga o processo de resposta a incidentes do ambiente.
