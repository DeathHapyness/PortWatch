# ADR-0001 — Backend como processo único (API + Collector)

## Status
Aceito.

## Contexto
O blueprint de arquitetura desenhou API e Collector como componentes lógicos
distintos, mas deixou em aberto se rodam como processos/containers separados
ou juntos. Separá-los exigiria algum mecanismo de IPC (fila, HTTP interno,
socket) só para o Collector empurrar estado para a API.

## Decisão
API e Collector rodam no mesmo processo Python (`portwatch_backend`), como
módulos internos (`api/`, `collector/`) compartilhando um estado em memória.
O Collector roda em thread(s)/tasks de background geridas pelo lifespan do
FastAPI (a partir da Fase 3), nunca bloqueando o event loop das requisições.

## Consequências
- Sem IPC, sem fila de mensagens, sem segundo container para a lógica de
  coleta — mais simples de rodar, testar e depurar num homelab de host único.
- Se no futuro surgir necessidade real de escalar o Collector
  independentemente da API (ex.: monitorar múltiplos hosts Docker), a
  separação em processos fica mais cara de introduzir depois — aceito como
  trade-off deliberado por simplicidade agora (ver regra "evitar
  infraestrutura por possibilidade futura").
