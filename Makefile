.PHONY: install train test lint clean

install:
	python -m pip install -e ".[dev]"

train:
	python -m healthai.train --config configs/baseline.yaml

test:
	python -m pytest

lint:
	python -m ruff check src tests

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov

