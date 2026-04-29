DOCKER ?= docker
COMPOSE ?= $(DOCKER) compose
IMAGE ?= mrfrederic/ifly-time-bot

.PHONY: up down logs rebuild-bot build-latest push-latest release-latest build-stable push-stable release-stable build-frontend frontend-dev

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f bot

rebuild-bot:
	$(COMPOSE) build --no-cache bot

build-frontend:
	cd frontend && (command -v bun >/dev/null 2>&1 && bun install && bun run build || npm install && npm run build)

frontend-dev:
	cd frontend && (command -v bun >/dev/null 2>&1 && bun install && bun run dev || npm install && npm run dev)

build-latest:
	$(DOCKER) build -t $(IMAGE):latest .

push-latest:
	$(DOCKER) push $(IMAGE):latest

release-latest: build-latest push-latest

build-stable:
	$(DOCKER) build -t $(IMAGE):stable .

push-stable:
	$(DOCKER) push $(IMAGE):stable

release-stable: build-stable push-stable