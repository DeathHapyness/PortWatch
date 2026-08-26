# ADR-0007 — Orçamento de coleta e backpressure

**Status:** aceito

## Contexto

Cada ciclo do Collector lista recursos e faz um `inspect` síncrono por
container e rede. Sem limites, o fan-out cresce linearmente com o Docker host:
um daemon comprometido ou uma instalação muito maior que o escopo de homelab
pode manter a thread ocupada por tempo indefinido e ampliar consumo de memória.

O snapshot é atômico. Publicar apenas os primeiros recursos ao atingir um
limite faria containers desaparecerem da API sem terem desaparecido do Docker,
portanto truncamento silencioso não é uma opção segura.

## Decisão

Cada ciclo recebe três limites configuráveis:

- `PORTWATCH_COLLECTOR_CYCLE_BUDGET_SECONDS` (padrão: 25);
- `PORTWATCH_COLLECTOR_MAX_CONTAINERS` (padrão: 1000);
- `PORTWATCH_COLLECTOR_MAX_NETWORKS` (padrão: 1000).

O deadline monotônico é verificado antes e depois das operações remotas e entre
inspeções. As listas retornadas pelo Docker são recusadas integralmente quando
excedem o limite configurado. Em qualquer estouro, o ciclo falha e o
`SnapshotStore` mantém a última geração completa; readiness e métricas já
expõem que ela está ficando stale e que houve falha de coleta.

O deadline é cooperativo: uma chamada síncrona em andamento não é cancelada no
meio, porque matar a thread ou publicar estado parcial violaria invariantes
mais importantes. O timeout de transporte do Docker e o timeout do netprobe
continuam limitando quanto uma única operação pode ultrapassar o deadline.

## Consequências

- Carga e tempo de ciclo ficam limitados por configuração explícita.
- Nunca há snapshot truncado apresentado como completo.
- Instalações legítimas acima dos padrões precisam elevar os limites.
- Um ciclo pode ultrapassar o orçamento por até o timeout da operação remota em
  andamento; cancelamento preemptivo exigiria trocar o modelo síncrono aprovado
  na ADR-0001 e fica fora da v1.
