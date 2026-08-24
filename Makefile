.PHONY: dev-up dev-down dev-status dev-guard

DEV_COMPOSE := infra/dev/docker-compose.dev.yml

dev-guard:
	@bash infra/dev/guard.sh

dev-up: dev-guard
	docker compose -f $(DEV_COMPOSE) up -d
	docker compose -f $(DEV_COMPOSE) ps

dev-down:
	docker compose -f $(DEV_COMPOSE) down -v

dev-status:
	docker compose -f $(DEV_COMPOSE) ps
