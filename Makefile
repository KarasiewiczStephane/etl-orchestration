.PHONY: install test lint clean run docker docker-up docker-down docker-logs docker-build docker-shell dbt-run dbt-docs quality-check format metrics-report

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

docker-up:
	docker compose up -d
	@echo "Airflow UI: http://localhost:8080 (admin/admin)"
	@echo "Mock API:   http://localhost:5000/api/health"

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f

docker-build:
	docker compose build --no-cache

docker-shell:
	docker compose exec airflow-webserver bash

dbt-run:
	cd dbt_project && dbt run --profiles-dir .

dbt-docs:
	cd dbt_project && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .

quality-check:
	python -m src.quality.checks

metrics-report:
	python -c "from src.monitoring.metrics import MetricsCollector; print(MetricsCollector().generate_report())"
