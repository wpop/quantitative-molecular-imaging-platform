.PHONY: backend-check backend-lint backend-typecheck backend-quality services-config services-up services-down services-logs services-ps

backend-check:
	cd backend && python manage.py check --settings=config.settings.development
	cd backend && python manage.py check --settings=config.settings.test

backend-lint:
	cd backend && ruff check .

backend-typecheck:
	cd backend && mypy .

backend-quality: backend-check backend-lint backend-typecheck

services-config:
	docker compose config

services-up:
	docker compose up -d postgres redis orthanc

services-down:
	docker compose down

services-logs:
	docker compose logs -f postgres redis orthanc

services-ps:
	docker compose ps
