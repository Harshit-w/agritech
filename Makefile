# AgriTech v3 — Makefile
# Usage: make <target>

.PHONY: run dev install install-ml test test-cov lint format clean docker docker-stop help

# ── Dev ───────────────────────────────────────────────────────────────────────
run:
	python app.py

dev:
	FLASK_DEBUG=1 python app.py

wsgi-run:
	gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 wsgi:application

# ── Install ───────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

install-ml:
	pip install -r requirements-ml.txt

install-dev:
	pip install -r requirements.txt pytest pytest-cov black flake8 isort

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=api --cov=services --cov=ml_service \
	  --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

test-fast:
	pytest tests/ -x -q

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	flake8 api/ services/ ml_service/ app.py config.py --max-line-length=110

format:
	black api/ services/ ml_service/ app.py config.py wsgi.py --line-length=110
	isort api/ services/ ml_service/ app.py config.py wsgi.py

# ── Docker ────────────────────────────────────────────────────────────────────
docker:
	docker-compose up -d --build
	@echo "Running at http://localhost:5000"

docker-stop:
	docker-compose down

docker-logs:
	docker-compose logs -f

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned build artifacts"

seed:
	python scripts/seed_data.py

train:
	python scripts/train_models.py

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "AgriTech v3 — Available commands:"
	@echo ""
	@echo "  make install      Install core dependencies (Flask)"
	@echo "  make install-ml   Install optional ML packages"
	@echo "  make install-dev  Install all + dev tools"
	@echo "  make run          Start development server"
	@echo "  make dev          Start with debug mode on"
	@echo "  make wsgi-run     Start production Gunicorn server"
	@echo "  make test         Run full test suite"
	@echo "  make test-cov     Run tests with coverage report"
	@echo "  make lint         Check code style"
	@echo "  make format       Auto-format code"
	@echo "  make docker       Build and start Docker containers"
	@echo "  make docker-stop  Stop Docker containers"
	@echo "  make clean        Remove build artifacts"
	@echo "  make seed         Seed sample data"
	@echo "  make train        Run ML training scripts"
	@echo ""
