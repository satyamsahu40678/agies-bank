.PHONY: setup dev build test check

setup:
	bash scripts/setup.sh

dev:
	bash scripts/dev.sh

build:
	cd frontend && npm run build

test:
	cd backend && .venv/bin/python -m pytest -q

check:
	bash scripts/check.sh
