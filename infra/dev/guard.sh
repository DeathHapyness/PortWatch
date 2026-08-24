#!/usr/bin/env bash
# Guarda de segurança: recusa operar o sandbox de dev se o Docker "de destino"
# não for, comprovadamente, o Docker local de desenvolvimento (contexto
# `default`, socket unix local, sem sinais de conter serviços reais). Não é
# prova criptográfica de nada — é um freio simples e barato contra apontar o
# sandbox, por engano, para o Docker do homelab de produção.
#
# Uso: infra/dev/guard.sh
#   Mensagens de diagnóstico vão para stderr. Em caso de sucesso, a ÚNICA
#   linha impressa em stdout é o endpoint Docker efetivo resolvido — para ser
#   capturado pelo Makefile e reaproveitado explicitamente na mesma operação
#   (up/down/status), fechando a janela de TOCTOU entre validar e agir.

set -euo pipefail

HARD_MAX_UNLABELED=10
requested_max_unlabeled="${PORTWATCH_DEV_MAX_UNLABELED:-5}"
if [ "$requested_max_unlabeled" -gt "$HARD_MAX_UNLABELED" ]; then
  # Teto absoluto: PORTWATCH_DEV_MAX_UNLABELED não pode virar bypass do guard.
  max_unlabeled_containers="$HARD_MAX_UNLABELED"
else
  max_unlabeled_containers="$requested_max_unlabeled"
fi

fail() {
  echo "✗ guard: $1" >&2
  echo "  Esta stack de dev só deve rodar contra o Docker local desta máquina (contexto 'default')." >&2
  echo "  Nenhum agente tem autorização para tocar o Docker de produção do homelab." >&2
  exit 1
}

# 1. O contexto Docker ativo precisa ser exatamente 'default'. Isso cobre tanto
#    um `docker context use` para outro contexto quanto um override via
#    DOCKER_CONTEXT — nenhum dos dois é aceito, mesmo que aponte, por acaso,
#    para um socket unix local.
context_name="$(docker context show 2>/dev/null || echo "")"
if [ "$context_name" != "default" ]; then
  fail "contexto Docker ativo é '${context_name:-<indisponível>}', não 'default'."
fi

# 2. O endpoint efetivamente usado pelo CLI Docker precisa ser um socket unix
#    local. DOCKER_HOST, quando definido, tem prioridade sobre o endpoint do
#    contexto — então validamos o valor que de fato será usado, não só um dos
#    dois.
effective_endpoint="${DOCKER_HOST:-}"
if [ -z "$effective_endpoint" ]; then
  effective_endpoint="$(docker context inspect --format '{{ (index .Endpoints "docker").Host }}' default 2>/dev/null || echo "")"
fi
case "$effective_endpoint" in
  unix:///*) ;; # ok — socket local
  *) fail "endpoint Docker efetivo não é um socket unix local: '${effective_endpoint:-<vazio>}'." ;;
esac

# 3. Heurística: se já existem muitos containers (rodando OU parados) sem o
#    label do sandbox, é mais provável que isto seja um Docker "de verdade"
#    com serviços reais do que o sandbox de dev vazio. Container parado ainda
#    pode ser produção — por isso `-a`, não só os em execução.
unlabeled="$(docker ps -a --format '{{.Label "portwatch.env"}}' | grep -vc '^dev-sandbox$' || true)"
if [ "$unlabeled" -gt "$max_unlabeled_containers" ]; then
  fail "$unlabeled container(s) (incluindo parados) sem o label portwatch.env=dev-sandbox (limite: $max_unlabeled_containers, teto absoluto: $HARD_MAX_UNLABELED). Isso não parece um Docker de dev vazio — abortando por segurança."
fi

echo "✓ guard: Docker local de desenvolvimento confirmado (contexto 'default', $unlabeled container(s) não rotulado(s), limite $max_unlabeled_containers)." >&2
printf '%s\n' "$effective_endpoint"
