#!/usr/bin/env bash
# Guarda de segurança: recusa operar o sandbox de dev se o Docker "de destino"
# não parecer, com boa confiança, ser o Docker local de desenvolvimento desta
# máquina (contexto `default`, socket unix canônico `/var/run/docker.sock`,
# sem sinais de conter serviços reais). Isto é uma heurística barata contra
# erro operacional — não é prova criptográfica nem isolamento de segurança
# forte, e falha fechado (rejeita) sempre que um valor não puder ser
# interpretado com confiança.
#
# Uso: infra/dev/guard.sh
#   Mensagens de diagnóstico vão para stderr. Em caso de sucesso, a ÚNICA
#   linha impressa em stdout é o endpoint Docker efetivo resolvido — para ser
#   capturado pelo Makefile e reaproveitado explicitamente na mesma operação
#   (up/down/status), fechando a janela de TOCTOU entre validar e agir.

set -euo pipefail

CANONICAL_ENDPOINT="unix:///var/run/docker.sock"
DEFAULT_MAX_UNLABELED=5

ps_tmp="$(mktemp)"
trap 'rm -f "$ps_tmp"' EXIT

fail() {
  echo "✗ guard: $1" >&2
  echo "  Esta stack de dev só deve rodar contra o Docker local desta máquina (contexto 'default', socket $CANONICAL_ENDPOINT)." >&2
  echo "  Nenhum agente tem autorização para tocar o Docker de produção do homelab." >&2
  exit 1
}

# 0. PORTWATCH_DEV_MAX_UNLABELED, se definido, precisa ser um inteiro decimal
#    não negativo — um valor inválido é rejeitado (falha fechada) em vez de
#    silenciosamente desativar a heurística do passo 3 (era o bypass INC-01).
#    O override só pode tornar o guard mais estrito (menor que o padrão),
#    nunca mais permissivo — não existe forma de "aumentar" o limite (INC-03).
requested_max_unlabeled="${PORTWATCH_DEV_MAX_UNLABELED:-$DEFAULT_MAX_UNLABELED}"
case "$requested_max_unlabeled" in
  ''|*[!0-9]*) fail "PORTWATCH_DEV_MAX_UNLABELED='$requested_max_unlabeled' não é um inteiro decimal não negativo." ;;
esac
if [ "$requested_max_unlabeled" -lt "$DEFAULT_MAX_UNLABELED" ]; then
  max_unlabeled_containers="$requested_max_unlabeled"
else
  max_unlabeled_containers="$DEFAULT_MAX_UNLABELED"
fi

# 1. O contexto Docker ativo precisa ser exatamente 'default'. Isso cobre tanto
#    um `docker context use` para outro contexto quanto um override via
#    DOCKER_CONTEXT — nenhum dos dois é aceito, mesmo que aponte, por acaso,
#    para o socket canônico.
context_name="$(docker context show 2>/dev/null || echo "")"
if [ "$context_name" != "default" ]; then
  fail "contexto Docker ativo é '${context_name:-<indisponível>}', não 'default'."
fi

# 2. O endpoint efetivamente usado pelo CLI Docker precisa ser exatamente o
#    socket canônico deste host (CLAUDE.md: "unix:///var/run/docker.sock
#    local"). DOCKER_HOST, quando definido, tem prioridade sobre o endpoint do
#    contexto — validamos o valor que de fato será usado, não só um dos dois.
#    Diferente da versão anterior, não aceitamos "qualquer" socket unix (era
#    o bypass INC-02): só o socket canônico exato é permitido.
effective_endpoint="${DOCKER_HOST:-}"
if [ -z "$effective_endpoint" ]; then
  effective_endpoint="$(docker context inspect --format '{{ (index .Endpoints "docker").Host }}' default 2>/dev/null || echo "")"
fi
if [ "$effective_endpoint" != "$CANONICAL_ENDPOINT" ]; then
  fail "endpoint Docker efetivo é '${effective_endpoint:-<vazio>}', esperado exatamente '$CANONICAL_ENDPOINT'."
fi

# 3. Heurística: se já existem muitos containers (rodando OU parados) sem o
#    label do sandbox, é mais provável que isto seja um Docker "de verdade"
#    com serviços reais do que o sandbox de dev vazio. Container parado ainda
#    pode ser produção — por isso `-a`, não só os em execução.
#    Falha de "docker ps" (daemon indisponível, permissão negada, etc.) tem
#    que travar o guard, não ser tratada como "0 containers não rotulados" —
#    por isso a checagem de erro fica separada da contagem via grep, e usamos
#    um arquivo temporário (não uma variável) para preservar corretamente o
#    caso de zero containers (uma variável vazia + printf criaria uma linha
#    em branco fantasma e contaria 1 não rotulado onde na verdade há 0).
if ! docker ps -a --format '{{.Label "portwatch.env"}}' >"$ps_tmp" 2>&1; then
  fail "'docker ps -a' falhou ao consultar o Docker: $(cat "$ps_tmp")"
fi
unlabeled="$(grep -vc '^dev-sandbox$' "$ps_tmp" || true)"
if [ "$unlabeled" -gt "$max_unlabeled_containers" ]; then
  fail "$unlabeled container(s) (incluindo parados) sem o label portwatch.env=dev-sandbox (limite: $max_unlabeled_containers). Isso não parece um Docker de dev vazio — abortando por segurança."
fi

echo "✓ guard: Docker local de desenvolvimento confirmado (contexto 'default', socket $CANONICAL_ENDPOINT, $unlabeled container(s) não rotulado(s), limite $max_unlabeled_containers)." >&2
printf '%s\n' "$effective_endpoint"
