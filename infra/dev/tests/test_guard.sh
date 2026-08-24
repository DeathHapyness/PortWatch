#!/usr/bin/env bash
# Testes automatizados de infra/dev/guard.sh usando um `docker` fake
# (fake-docker.sh) — nunca toca no Docker real desta máquina.
#
# Uso: bash infra/dev/tests/test_guard.sh
#
# Cobre o achado INC-04 (revisão incremental de docs/audits/): sucesso,
# contexto remoto, endpoint TCP, socket unix alternativo, inspect vazio,
# falha do daemon, valores inválidos de PORTWATCH_DEV_MAX_UNLABELED, e o
# padrão usado pelo Makefile onde uma falha do guard não pode deixar a
# receita continuar até o `docker compose`.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/../guard.sh"
FAKE_BIN_DIR="$(mktemp -d)"
cp "$HERE/fake-docker.sh" "$FAKE_BIN_DIR/docker"
chmod +x "$FAKE_BIN_DIR/docker"
STDOUT_FILE="$(mktemp)"
STDERR_FILE="$(mktemp)"
cleanup() { rm -rf "$FAKE_BIN_DIR" "$STDOUT_FILE" "$STDERR_FILE"; }
trap cleanup EXIT

PASS=0
FAIL=0

# Roda guard.sh com PATH controlado (fake docker primeiro) e ambiente
# isolado — só o que o teste passar como VAR=val em "$@" chega ao guard.
run_guard() {
  env -i PATH="$FAKE_BIN_DIR:/usr/bin:/bin" HOME="${HOME:-/tmp}" "$@" bash "$GUARD" \
    >"$STDOUT_FILE" 2>"$STDERR_FILE"
}

expect_pass() {
  local name="$1"; shift
  local status=0
  run_guard "$@" || status=$?
  if [ "$status" -eq 0 ]; then
    echo "ok - $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL - $name: esperado sucesso (exit 0), obtido exit $status"
    sed 's/^/    stderr: /' "$STDERR_FILE"
    FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1"; shift
  local status=0
  run_guard "$@" || status=$?
  if [ "$status" -ne 0 ]; then
    echo "ok - $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL - $name: esperado falha (exit != 0), guard aprovou"
    FAIL=$((FAIL + 1))
  fi
}

# --- casos: contexto e endpoint ---

expect_pass "contexto default + socket canônico + sandbox vazio => aprova" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock

expect_fail "contexto nomeado/remoto (ex.: homelab-prod) => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=homelab-prod \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock

expect_fail "endpoint TCP => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=tcp://10.0.0.5:2375

expect_fail "socket unix alternativo/não canônico => rejeita (INC-02)" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///tmp/algum-outro.sock

expect_fail "DOCKER_HOST para socket alternativo, mesmo com contexto default => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  DOCKER_HOST=unix:///tmp/outro-daemon.sock

expect_fail "inspect de endpoint vazio (contexto sem endpoint resolvido) => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=

expect_fail "'docker context show' falha (daemon indisponível) => rejeita" \
  FAKE_DOCKER_CONTEXT_SHOW_FAIL=1

expect_fail "'docker ps' falha (daemon indisponível) => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_FAIL=1

# --- casos: heurística de containers não rotulados ---

expect_pass "containers existentes todos rotulados dev-sandbox => aprova" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'dev-sandbox\ndev-sandbox\ndev-sandbox\n')"

expect_fail "containers não rotulados acima do limite padrão (6 > 5) => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\n')"

# --- casos: PORTWATCH_DEV_MAX_UNLABELED inválido (INC-01) ---
# Um valor inválido tem que ser REJEITADO, nunca desativar silenciosamente a
# heurística acima (era exatamente o bypass do INC-01).

expect_fail "PORTWATCH_DEV_MAX_UNLABELED não numérico => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\n')" \
  PORTWATCH_DEV_MAX_UNLABELED=abc

expect_fail "PORTWATCH_DEV_MAX_UNLABELED negativo => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  PORTWATCH_DEV_MAX_UNLABELED=-1

expect_fail "PORTWATCH_DEV_MAX_UNLABELED decimal => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  PORTWATCH_DEV_MAX_UNLABELED=2.5

expect_pass "PORTWATCH_DEV_MAX_UNLABELED definido vazio é tratado como não definido (usa o padrão) => aprova" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  PORTWATCH_DEV_MAX_UNLABELED=""

expect_fail "PORTWATCH_DEV_MAX_UNLABELED com espaço embutido => rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  PORTWATCH_DEV_MAX_UNLABELED="3 "

# --- casos: teto do override (INC-03) — só pode reduzir o limite, nunca aumentar ---

expect_pass "override acima do padrão não eleva o limite além de 5: 5 não rotulados ainda aprova" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\n')" \
  PORTWATCH_DEV_MAX_UNLABELED=9999

expect_fail "override acima do padrão não eleva o limite além de 5: 6 não rotulados ainda rejeita" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\nunlabeled\n')" \
  PORTWATCH_DEV_MAX_UNLABELED=9999

expect_pass "override abaixo do padrão reduz o limite de fato: 2 não rotulados aprova com limite 3" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\n')" \
  PORTWATCH_DEV_MAX_UNLABELED=3

expect_fail "override abaixo do padrão reduz o limite de fato: 3 não rotulados rejeita com limite 2" \
  FAKE_DOCKER_CONTEXT_NAME=default \
  FAKE_DOCKER_CONTEXT_ENDPOINT=unix:///var/run/docker.sock \
  FAKE_DOCKER_PS_OUTPUT="$(printf 'unlabeled\nunlabeled\nunlabeled\n')" \
  PORTWATCH_DEV_MAX_UNLABELED=2

# --- padrão do Makefile: falha do guard não pode deixar a receita seguir ---

echo "---"
recipe_script="$(mktemp)"
cat >"$recipe_script" <<EOF
endpoint="\$(bash "$GUARD")"
echo "reached-compose: \$endpoint"
EOF
recipe_out=""
recipe_status=0
recipe_out="$(env -i PATH="$FAKE_BIN_DIR:/usr/bin:/bin" HOME="${HOME:-/tmp}" \
  FAKE_DOCKER_CONTEXT_SHOW_FAIL=1 \
  bash -eu -o pipefail "$recipe_script" 2>&1)" || recipe_status=$?
rm -f "$recipe_script"

if [ "$recipe_status" -eq 0 ] || printf '%s' "$recipe_out" | grep -q "reached-compose"; then
  echo "FAIL - padrão Makefile: guard falhou mas a receita chegou ao passo do compose"
  echo "    saída: $recipe_out"
  FAIL=$((FAIL + 1))
else
  echo "ok - padrão Makefile: receita abortou antes do passo do compose quando o guard falha"
  PASS=$((PASS + 1))
fi

echo "---"
echo "$PASS passou, $FAIL falhou"
[ "$FAIL" -eq 0 ]
