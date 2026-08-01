# Quantitative Molecular Imaging Platform

Quantitative Molecular Imaging Platform is a research backend for exploring
metadata-driven PET/CT molecular imaging workflows. It currently focuses on a
small, selected public deidentified TCIA dataset subset, local metadata
validation, metadata ingestion into PostgreSQL, and read-only REST APIs for
technical review.

This repository is not a clinical product and must not be used for diagnosis,
treatment decisions, or production patient care.

## Architecture

- Django and Django REST Framework provide the backend API.
- PostgreSQL stores imaging metadata and ingestion job metadata.
- Redis is configured for Celery broker and result backend support.
- Orthanc is available as a local research PACS service, but the current
  metadata API reads PostgreSQL only.
- Local utility scripts support optional real-data metadata query, selected
  series download, checksum/header validation, and metadata ingestion.

The API is read-only and metadata-only. It does not read raw DICOM files, expose
raw DICOM content, expose pixel data, or perform image analysis.

## Requirements

- Python 3.12
- Docker with Docker Compose
- PostgreSQL and Redis, usually started through Docker Compose
- A local Python environment with backend dependencies installed

Install backend dependencies from the backend package:

```sh
python -m pip install -e "backend[dev]"
```

## Environment

Copy `.env.example` to `.env` for local development values, or export the same
variables in your shell. Do not commit local environment files.

Important variables:

- `DJANGO_SETTINGS_MODULE=config.settings.development`
- `POSTGRES_DB=qmip`
- `POSTGRES_USER=qmip`
- `POSTGRES_PASSWORD=qmip_dev_password`
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`

## Local Setup

Start local services:

```sh
make services-up
```

Apply migrations:

```sh
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py migrate --settings=config.settings.development
```

Run the development server:

```sh
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py runserver --settings=config.settings.development
```

Useful service URLs:

- Backend API: `http://localhost:8000/api/v1/`
- Orthanc HTTP UI and REST API: `http://localhost:8042`
- Orthanc DICOM listener: `localhost:4242`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Optional Real-Data Workflow

The selected candidate collection is `CT-vs-PET-Ventilation-Imaging`. The
optional local subset contains CT and PT series for subject `CT-PET-VI-01`.

Raw DICOM files are never stored in Git. Optional local DICOM files remain under
`datasets/raw/`, which is for local validation only and is not required by CI.

Workflow scripts:

- `scripts/query_tcia_metadata.py`
- `scripts/download_tcia_selected_series.py`
- `scripts/validate_local_dicom_subset.py`
- `scripts/ingest_local_dicom_metadata.py`
- `scripts/run_local_demo_pipeline.py`

See [docs/local_workflow.md](docs/local_workflow.md) for the command sequence.

For a one-command local backend demo after the selected DICOM subset is already
downloaded locally:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/run_local_demo_pipeline.py
```

The demo validates local data, ingests metadata, runs the metadata-only geometry
summary, and prints database counts. It does not download data or read pixel
arrays.

## API Usage

Read-only metadata endpoints:

- `GET /api/v1/overview/`
- `GET /api/v1/imaging/studies/`
- `GET /api/v1/imaging/series/`
- `GET /api/v1/imaging/instances/`
- `GET /api/v1/ingestion/jobs/`
- `GET /api/v1/ingestion/events/`

See [docs/api_usage.md](docs/api_usage.md) for curl examples and query
parameters.

## Quality Checks

Run from the repository root:

```sh
POSTGRES_PASSWORD=qmip_dev_password pytest
```

Run backend checks from `backend/`:

```sh
python manage.py check --settings=config.settings.development
python manage.py check --settings=config.settings.test
ruff check .
mypy .
```

The Makefile also provides:

```sh
make backend-quality
```

## Safety Notes

- Use public deidentified datasets only.
- Do not commit raw DICOM files, derived medical images, private environment
  files, patient records, or secrets.
- The current API reads PostgreSQL metadata only.
- Local ingestion reads DICOM headers only with `pydicom` and
  `stop_before_pixels=True`.
- Optional local data is for development validation, not CI or production use.
