.PHONY: install test lint clean run docker airflow-up airflow-down dbt-run quality-check format metrics-report

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/ --fix
	ruff format src/ tests/

format:
	ruff format src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov

run:
	python -m src.main

docker:
	docker build -t $(shell basename $(CURDIR)) .
	docker run -p 8000:8000 $(shell basename $(CURDIR))

airflow-up:
	docker compose up -d

airflow-down:
	docker compose down

dbt-run:
	cd dbt_project && dbt run --profiles-dir .

quality-check:
	python -m src.quality.checks

metrics-report:
	python -c "from src.monitoring.metrics import MetricsCollector; print(MetricsCollector().generate_report())"
