.PHONY: setup dev build test test-firestore check deploy

setup:
	bash scripts/setup.sh

dev:
	bash scripts/dev.sh

build:
	cd frontend && npm run build

test:
	cd backend && .venv/bin/python -m pytest -q

test-firestore:
	bash scripts/test-firestore.sh

deploy:
	bash scripts/deploy-google.sh

check:
	bash scripts/check.sh
