.PHONY: setup test lint smoke pilot build eval eval-real report demo verify-all

setup:
	pip install -r requirements.txt && playwright install --with-deps chromium

test:
	python -m pytest -q

lint:
	python -m ruff check . && python -m ruff format --check .

smoke:
	python scripts/smoke_test.py

pilot:
	python scripts/smoke_test.py && python -m sanket.cli pilot

build:
	python -m sanket.cli build

eval:
	python -m sanket.cli eval

eval-real:
	python -m sanket.cli eval --set real

report:
	python -m sanket.cli report

demo:
	python -m streamlit run demo/app.py --server.port 8501 --server.address 0.0.0.0

verify-all: lint test smoke
