COMPOSE := COMPOSE_BAKE=true docker compose --env-file .env

.PHONY: up down build rebuild logs ps restart bake bake-print

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

rebuild: down build up

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

restart: down up

# bake with TAG and/or REGISTRY:  make bake TAG=v1 REGISTRY=ghcr.io/you
bake:
	TAG=$(TAG) REGISTRY=$(REGISTRY) docker buildx bake $(TARGET)

bake-print:
	TAG=$(TAG) REGISTRY=$(REGISTRY) docker buildx bake --print $(TARGET)

# ---- Service-specific shortcuts ----

# Rebuild app image (Playwright + Chromium) and start stack dependencies
up-app:
	$(COMPOSE) up -d postgres redis keystroke-ml mailhog app --build

up-ml:
	$(COMPOSE) up -d keystroke-ml --build

up-db:
	$(COMPOSE) up -d postgres redis

logs-app:
	$(COMPOSE) logs -f app

logs-ml:
	$(COMPOSE) logs -f keystroke-ml

logs-db:
	$(COMPOSE) logs -f postgres redis
