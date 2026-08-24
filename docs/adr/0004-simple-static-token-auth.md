# ADR-0004 — Autenticação: token estático simples na v1

## Status
Aceito.

## Contexto
PortWatch roda num homelab de host único, tipicamente atrás de rede
confiável ou de uma solução de acesso já existente do usuário (ex.:
Tailscale, Authelia). Um sistema de contas/OAuth próprio seria complexidade
sem necessidade concreta nesta fase.

## Decisão
Autenticação da v1 é um único token estático (bearer), lido de variável de
ambiente. Sem contas de usuário, sem OAuth, sem sessões. Bind padrão em
`127.0.0.1`; exposição em LAN/remota é opt-in explícito do usuário, e nesse
caso o token passa a ser obrigatório.

## Consequências
- Implementação e revisão de segurança triviais.
- Não há multiusuário nem permissões por papel — se isso vier a ser
  necessário, é uma decisão nova, não uma extensão incremental desta ADR.
