.PHONY: install data train migrate migration api frontend test test-backend test-frontend lint clean

install:
	python -m pip install -e ".[dev]"

data:
	python scripts/download_datasets.py

train:
	python -m healthai.train --config configs/models.yaml

migrate:
	python -m alembic upgrade head

migration:
	@test -n "$(message)" || (echo "Use: make migration message='descricao'" && exit 1)
	python -m alembic revision --autogenerate -m "$(message)"

api:
	uvicorn backend.app:app --reload --port 8000

frontend:
	npm --prefix frontend run dev

test: test-backend test-frontend

test-backend:
	python -m pytest

test-frontend:
	npm --prefix frontend test

lint:
	python -m ruff check backend migrations src tests

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov
