# Quantitative Molecular Imaging Platform

Quantitative Molecular Imaging Platform is a research and portfolio backend for
exploring PET/CT molecular imaging workflows. The project is currently in the
foundation stage: local service infrastructure, Django configuration, and code
quality checks are being established before models, APIs, dataset ingestion, or
scientific algorithms are added.

This repository is not a clinical product and must not be used for diagnosis,
treatment decisions, or production patient care.

## Local Services

Local development uses:

- PostgreSQL for the backend database
- Redis for Celery broker and result backend
- Orthanc as a local research PACS service with DICOMweb enabled

PostgreSQL is the only project database. SQLite is not configured or used as a
fallback.

## Data Safety

Use public, deidentified datasets only. Do not commit real downloaded medical
imaging files, generated derived volumes, patient records, local secrets, or
private environment files. The `datasets/downloads/` and `datasets/derived/`
directories are intentionally ignored except for their local `.gitignore` guard
files.

## Local Development

Copy `.env.example` into a local environment file if needed and replace only
local development values. Do not commit local environment files.

Start local services:

```sh
make services-up
```

Inspect service configuration and status:

```sh
make services-config
make services-ps
```

Run backend checks:

```sh
make backend-quality
```

Stop local services:

```sh
make services-down
```

Useful service URLs:

- Orthanc HTTP UI and REST API: `http://localhost:8042`
- Orthanc DICOM listener: `localhost:4242`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
