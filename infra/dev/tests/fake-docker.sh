#!/usr/bin/env bash
# `docker` fake usada só por infra/dev/tests/test_guard.sh — nunca chama um
# daemon real. Comportamento controlado inteiramente por variáveis de
# ambiente FAKE_DOCKER_*, lidas aqui e setadas pelo script de teste.
#
# Suporta só os subcomandos que infra/dev/guard.sh realmente usa:
#   docker context show
#   docker context inspect --format '...' default
#   docker ps -a --format '...'

set -euo pipefail

sub="${1:-}"
sub2="${2:-}"

if [ "$sub" = "context" ] && [ "$sub2" = "show" ]; then
  if [ "${FAKE_DOCKER_CONTEXT_SHOW_FAIL:-0}" = "1" ]; then
    exit 1
  fi
  printf '%s\n' "${FAKE_DOCKER_CONTEXT_NAME-default}"
  exit 0
fi

if [ "$sub" = "context" ] && [ "$sub2" = "inspect" ]; then
  if [ "${FAKE_DOCKER_CONTEXT_INSPECT_FAIL:-0}" = "1" ]; then
    exit 1
  fi
  printf '%s\n' "${FAKE_DOCKER_CONTEXT_ENDPOINT-unix:///var/run/docker.sock}"
  exit 0
fi

if [ "$sub" = "ps" ]; then
  if [ "${FAKE_DOCKER_PS_FAIL:-0}" = "1" ]; then
    exit 1
  fi
  if [ -n "${FAKE_DOCKER_PS_OUTPUT:-}" ]; then
    printf '%s\n' "${FAKE_DOCKER_PS_OUTPUT}"
  fi
  exit 0
fi

echo "fake-docker: comando não suportado no teste: $*" >&2
exit 99
