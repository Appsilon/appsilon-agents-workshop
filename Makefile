.PHONY: check format up down

check:
	cd backend && uv run ruff check .
	cd frontend && npm run lint && npm run build

format:
	cd backend && uv run ruff format .
	cd frontend && npm run format

up:
	docker compose up --build

down:
	docker compose down
