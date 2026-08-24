# Revisão incremental — correções do guard Docker

**Data:** 23/08/2026  
**Commit revisado:** `2c993b8` (`fix: close dev-sandbox guard bypass and TOCTOU`)  
**Relatório-base:** `docs/audits/2026-08-23-auditoria-tecnica.md`  
**Escopo:** revisão somente-leitura das correções de PW-01, PW-04 e PW-11.

## Resumo executivo

O commit corrige adequadamente o problema Critical de `dev-down` sem guard
(PW-01) e fecha a principal janela TOCTOU entre validação e execução (PW-11).
PW-04, entretanto, está apenas parcialmente resolvido.

A revisão encontrou um novo bypass High causado pela falta de validação do tipo
de `PORTWATCH_DEV_MAX_UNLABELED`. Também permanece a aceitação de qualquer socket
Unix, apesar de `CLAUDE.md` limitar o ambiente autorizado a
`unix:///var/run/docker.sock`.

Classificação desta rodada:

- **Critical:** 0
- **High:** 2
- **Medium:** 2
- **Low:** 1
- **Achados anteriores confirmadamente resolvidos:** 2

## Achados resolvidos

### RES-01 — PW-01: `dev-down` sem guard

**Localização:** `Makefile:22-24`.

**Avaliação:** resolvido. `dev-down` agora executa o guard antes do Compose e
reutiliza o endpoint retornado. A operação destrutiva não ignora mais a barreira
de segurança.

### RES-02 — PW-11: TOCTOU baseado em mudança de contexto

**Localização:** `Makefile:17-28` e `infra/dev/guard.sh:45-52`.

**Avaliação:** resolvido para o cenário identificado. O endpoint é resolvido uma
vez, capturado na mesma receita shell e passado explicitamente ao Compose via
`DOCKER_HOST`. Uma mudança posterior do contexto global deixa de redirecionar a
operação.

## High

### INC-01 — Valor não numérico desativa a heurística de containers

**Localização:** `infra/dev/guard.sh:16-23` e `58-61`.

**Motivo:** `requested_max_unlabeled` é usado em comparações `-gt` sem validação
prévia. Dentro de um `if`, uma falha de `[` não encerra o script mesmo com
`set -e`. Por exemplo, com:

```sh
PORTWATCH_DEV_MAX_UNLABELED=abc
```

a primeira comparação falha e entra no `else`, armazenando `abc` em
`max_unlabeled_containers`. A segunda comparação também falha como condição
falsa, permitindo que o guard continue.

**Impacto:** uma variável de ambiente inválida pode desativar a principal
heurística contra uso do daemon errado. O guard pode aprovar um Docker com
qualquer quantidade de containers não rotulados.

**Correção recomendada:** validar antes de qualquer operação aritmética usando
uma expressão estrita para inteiro decimal não negativo, rejeitando o valor em
vez de normalizá-lo silenciosamente. Adicionar testes para texto, espaços,
decimal, número negativo, vazio e valor acima do teto.

### INC-02 — Socket Unix alternativo continua autorizado

**Localização:** `infra/dev/guard.sh:41-52` e `CLAUDE.md:14-20`.

**Motivo:** o case aceita `unix:///*`, enquanto a regra canônica autoriza apenas
o contexto `default` com `unix:///var/run/docker.sock`. `DOCKER_HOST` tem
prioridade e pode apontar para outro socket Unix mesmo quando
`docker context show` informa `default`.

**Impacto:** um socket de daemon remoto encaminhado/montado localmente ou um
segundo daemon de produção no host pode passar pelo guard.

**Correção recomendada:** rejeitar `DOCKER_HOST` definido, salvo se seu valor
canônico for exatamente o socket aprovado, e confirmar que o endpoint do
contexto `default` também corresponde ao valor esperado. Se rootless Docker
precisar ser suportado, isso deve virar uma decisão explícita com allowlist
controlada, não um wildcard.

## Medium

### INC-03 — Teto configurável ainda aceita até 10 containers não rotulados

**Localização:** `infra/dev/guard.sh:16-23`.

**Motivo:** o teto absoluto impede um valor ilimitado, mas aumentou o limite
possível de 5 para 10. Um daemon com até 10 containers reais continua sendo
considerado aceitável.

**Impacto:** a heurística pode aprovar um daemon pequeno de produção, caso os
controles de contexto/socket também sejam contornados.

**Correção recomendada:** preferir deny-by-default. Considerar zero containers
não rotulados para operações destrutivas, ou manter allowlist explícita de IDs,
labels e nome de projeto do sandbox. Se um limite for necessário, justificar o
valor em ADR e não permitir override em operações destrutivas.

### INC-04 — Correção de segurança sem testes automatizados

**Localização:** `infra/dev/guard.sh`, `Makefile` e ausência de testes em
`infra/dev/tests/` ou equivalente.

**Motivo:** a lógica depende de precedência entre `DOCKER_CONTEXT`,
`DOCKER_HOST`, saída do CLI, comparações shell e propagação pelo Makefile. O
bypass INC-01 é exatamente o tipo de regressão que testes com um CLI Docker fake
detectariam.

**Impacto:** futuras alterações podem reabrir bypasses sem falhar no CI.

**Correção recomendada:** testar o guard com um executável `docker` fake inserido
no `PATH`, sem acessar daemon real. Cobrir sucesso, contexto remoto, endpoint
TCP, socket alternativo, inspect vazio, falha do daemon, valores inválidos do
limite e confirmação de que `dev-down` não chega ao Compose quando o guard falha.

## Low

### INC-05 — Comentário afirma garantia mais forte que a implementação

**Localização:** `infra/dev/guard.sh:2-6`.

**Motivo:** o texto diz que o destino é “comprovadamente” o Docker local, mas a
verificação continua heurística e aceita qualquer socket Unix.

**Impacto:** revisores e operadores podem superestimar a proteção oferecida.

**Correção recomendada:** usar linguagem compatível com a garantia real até que
o endpoint seja validado estritamente.

## Validações realizadas

| Verificação | Resultado |
|---|---|
| `bash -n infra/dev/guard.sh` | Passou |
| `docker compose ... config --quiet` | Passou |
| `git diff --check` | Passou |
| Revisão estática do fluxo Make/guard | PW-01 e PW-11 resolvidos |
| Testes automatizados específicos do guard | Ausentes |

Nenhum container foi criado, parado ou removido. O socket Docker não foi usado
para executar o sandbox durante esta revisão.

## Prioridade recomendada

1. Corrigir INC-01 antes de considerar PW-04 encerrado.
2. Restringir o endpoint ao socket canônico autorizado (INC-02).
3. Adicionar testes do guard antes de novas mudanças no fluxo Docker.
4. Reavaliar ou remover o override de containers não rotulados.

