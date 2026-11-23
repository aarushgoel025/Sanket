.PHONY: setup test lint smoke pilot build eval eval-real report demo demo-streamlit dev-ui dev-api build-ui verify-all

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

build-ui:
	cd frontend && npm install && npm run build

dev-ui:
	cd frontend && npm run dev

dev-api:
	python -m uvicorn sanket.api.main:app --reload --port 8000

demo:
	python -m uvicorn sanket.api.main:app --host 0.0.0.0 --port 8501

demo-streamlit:
	python -m streamlit run demo/app.py --server.port 8501 --server.address 0.0.0.0

verify-all: lint test smoke
