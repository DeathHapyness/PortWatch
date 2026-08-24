SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: dev-up dev-down dev-status dev-guard test-e2e

DEV_COMPOSE := infra/dev/docker-compose.dev.yml

# Roda só a verificação, sem executar nenhuma operação no sandbox.
dev-guard:
	@bash infra/dev/guard.sh >/dev/null

# dev-up/down/status resolvem o endpoint Docker UMA vez via guard.sh e
# reaproveitam esse mesmo valor explicitamente no `docker compose` que segue,
# na mesma invocação de shell — em vez de confiar duas vezes (guard e depois
# compose) no contexto ambiente, que poderia mudar entre as duas chamadas
# (TOCTOU). Isso também garante que dev-down passe pelo guard como dev-up.
dev-up:
	@endpoint="$$(bash infra/dev/guard.sh)"; \
	DOCKER_HOST="$$endpoint" docker compose -f $(DEV_COMPOSE) up -d; \
	DOCKER_HOST="$$endpoint" docker compose -f $(DEV_COMPOSE) ps

dev-down:
	@endpoint="$$(bash infra/dev/guard.sh)"; \
	DOCKER_HOST="$$endpoint" docker compose -f $(DEV_COMPOSE) down -v

dev-status:
	@endpoint="$$(bash infra/dev/guard.sh)"; \
	DOCKER_HOST="$$endpoint" docker compose -f $(DEV_COMPOSE) ps

# apps/backend/tests/e2e/ manages its own guard->up->test->down lifecycle
# (see conftest.py) — this target is just a memorable entry point, same
# guard as everything else above.
test-e2e:
	cd apps/backend && uv run pytest -m e2e
