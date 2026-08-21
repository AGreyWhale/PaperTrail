SHELL := /bin/bash

ROOT     := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
BACKEND  := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend
VENV     := $(BACKEND)/.venv/bin

# Every recipe calls the venv binaries by absolute path, so none of these
# targets need `source .venv/bin/activate` first -- and none of them can
# accidentally pick up a system-wide alembic/uvicorn instead.

.DEFAULT_GOAL := dev
.PHONY: dev api web worker ports up down migrate test build install clean

## dev: containers + migrations, then API and web together (Ctrl-C stops both)
dev: ports migrate
	@echo ""
	@echo "  API   http://localhost:8000/docs"
	@echo "  Web   http://localhost:5173"
	@echo ""
	@trap 'kill 0' INT TERM; \
	  ( cd $(BACKEND) && $(VENV)/uvicorn app.main:app --reload --reload-dir app ) & \
	  ( cd $(FRONTEND) && pnpm dev ) & \
	  wait

## ports: refuse to start if 8000/5173 are taken. `dev` backgrounds both
## servers, so without this a bind failure scrolls past and you end up
## running half the stack against a stale process.
ports:
	@for p in 8000 5173; do \
	  if ss -tln "sport = :$$p" | grep -q LISTEN; then \
	    echo ""; \
	    echo "  Port $$p is already in use -- refusing to start."; \
	    ss -tlnp "sport = :$$p" | tail -n +2; \
	    echo ""; \
	    echo "  Stop it, then retry:   kill <pid>"; \
	    echo "  If it ignores SIGTERM: kill -9 <pid>"; \
	    echo ""; \
	    exit 1; \
	  fi; \
	done

## api: backend only, on top of containers + migrations
api: migrate
	cd $(BACKEND) && $(VENV)/uvicorn app.main:app --reload --reload-dir app

## web: frontend dev server only
web:
	cd $(FRONTEND) && pnpm dev

## worker: celery worker for embedding jobs (own terminal, alongside `make dev`)
worker: up
	cd $(BACKEND) && $(VENV)/celery -A app.workers.celery_app.celery_app worker --loglevel=info

## up: start postgres, redis and chroma, and wait until they accept connections
up:
	docker compose -f $(ROOT)/docker-compose.yml up -d --wait

## down: stop the containers (volumes, and so your data, are kept)
down:
	docker compose -f $(ROOT)/docker-compose.yml down

## migrate: bring the database schema up to head
migrate: up
	cd $(BACKEND) && $(VENV)/alembic upgrade head

## test: backend test suite
test:
	cd $(BACKEND) && $(VENV)/python -m pytest tests/ -q

## build: typecheck + production build of the frontend
build:
	cd $(FRONTEND) && pnpm build

## install: sync both dependency sets after a pull
install:
	cd $(BACKEND) && $(VENV)/pip install -r requirements.txt
	cd $(FRONTEND) && pnpm install

## clean: drop containers AND the postgres volume, wiping all data
clean:
	docker compose -f $(ROOT)/docker-compose.yml down -v
