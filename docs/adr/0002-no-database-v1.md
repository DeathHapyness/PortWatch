# ADR-0002 — Sem banco de dados na v1

## Status
Aceito.

## Contexto
Containers, portas, redes e status são sempre re-deriváveis ao vivo do Docker
e do host. Persistir esse estado criaria uma segunda fonte de verdade capaz
de divergir da real, sem benefício correspondente.

## Decisão
Nenhum banco de dados na v1. Estado central fica em memória no Collector
(TTL curto, invalidado por eventos). Séries temporais/tendências ficam a
cargo do Prometheus do próprio usuário, via scrape de `/metrics`.

## Consequências
- Menos infraestrutura para rodar, fazer backup e migrar.
- Reinício do PortWatch perde apenas cache — o estado real volta assim que o
  Collector reconsulta o Docker, não há dado "perdido".
- Se entrarem regras de alerta configuráveis, histórico de alertas, ou
  preferências multiusuário, o próximo passo natural é **SQLite** (arquivo
  único, sem servidor extra) — não Postgres, a menos que surja necessidade
  real de múltiplos escritores concorrentes.
