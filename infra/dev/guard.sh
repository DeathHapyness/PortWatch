#!/usr/bin/env bash
# Guarda de segurança: recusa operar o sandbox de dev se o Docker "de destino"
# não parecer ser o Docker local de desenvolvimento. Não é uma prova
# criptográfica de nada — é um freio simples e barato contra apontar o
# sandbox, por engano, para o Docker do homelab de produção.
#
# Uso: infra/dev/guard.sh   (chamado pelos alvos do Makefile antes de subir/derrubar o sandbox)

set -euo pipefail

MAX_UNLABELED_CONTAINERS="${PORTWATCH_DEV_MAX_UNLABELED:-5}"

fail() {
  echo "✗ guard: $1" >&2
  echo "  Esta stack de dev só deve rodar contra o Docker local desta máquina." >&2
  echo "  Nenhum agente tem autorização para tocar o Docker de produção do homelab." >&2
  exit 1
}

# 1. DOCKER_HOST, se definido, precisa apontar para um socket unix local.
if [ -n "${DOCKER_HOST:-}" ]; then
  case "$DOCKER_HOST" in
    unix:///*) ;; # ok, socket local
    *) fail "DOCKER_HOST='$DOCKER_HOST' aponta para um endpoint remoto/TCP." ;;
  esac
fi

# 2. O contexto Docker ativo precisa expor um endpoint unix local.
endpoint="$(docker context inspect --format '{{ (index .Endpoints "docker").Host }}' 2>/dev/null || echo "")"
case "$endpoint" in
  unix:///*|"") ;; # ok — socket local, ou docker antigo sem contexto explícito
  *) fail "contexto Docker ativo aponta para endpoint remoto: $endpoint" ;;
esac

# 3. Heurística: se já existem muitos containers rodando sem o label do
#    sandbox, é mais provável que isto seja um Docker "de verdade" com
#    serviços reais do que o sandbox de dev vazio.
unlabeled="$(docker ps --format '{{.Label "portwatch.env"}}' | grep -vc '^dev-sandbox$' || true)"
if [ "$unlabeled" -gt "$MAX_UNLABELED_CONTAINERS" ]; then
  fail "$unlabeled containers rodando sem o label portwatch.env=dev-sandbox (limite: $MAX_UNLABELED_CONTAINERS). Isso não parece um Docker de dev vazio — abortando por segurança."
fi

echo "✓ guard: Docker local de desenvolvimento confirmado ($unlabeled container(s) não rotulado(s), limite $MAX_UNLABELED_CONTAINERS)."
