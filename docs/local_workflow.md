# Local Workflow

This guide describes the local development workflow for the backend and the
optional selected real-data validation path. Raw DICOM files are optional,
local-only, and remain under `datasets/raw/`.

For a quick portfolio review, start local services, apply migrations, run the
one-command backend demo if the selected DICOM subset already exists locally,
then start the API and frontend dashboard.

## Environment Setup

Create and activate a Python 3.12 environment using your preferred tool. Then
install backend dependencies:

```sh
python -m pip install -e "backend[dev]"
```

Copy the example environment file if useful:

```sh
cp .env.example .env
```

For shell commands in this guide, ensure the PostgreSQL password is available:

```sh
export POSTGRES_PASSWORD=qmip_dev_password
```

## Services And Database

Start local services:

```sh
make services-up
```

Apply migrations:

```sh
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py migrate --settings=config.settings.development
cd ..
```

## Optional Real-Data Metadata Query

This step queries TCIA/NBIA metadata only. It does not download DICOM image
files.

```sh
python scripts/query_tcia_metadata.py \
  --collection CT-vs-PET-Ventilation-Imaging \
  --output-dir backend/tests/real_data/metadata_candidates \
  --max-series 2
```

## Optional Selected DICOM Download

This step downloads only the selected CT and PT series for local validation.
The full collection must not be downloaded for tests.

```sh
python scripts/download_tcia_selected_series.py
```

Raw DICOM files are written under:

```text
datasets/raw/tcia/CT-vs-PET-Ventilation-Imaging/CT-PET-VI-01/
```

These files are not committed to Git and are not required by CI.

## Local DICOM Validation

Validate checksums and DICOM headers without reading pixel arrays:

```sh
python scripts/validate_local_dicom_subset.py
```

The validator reads metadata only and does not perform image analysis.

## Local Metadata Ingestion

Ingest validated DICOM header metadata into PostgreSQL:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/ingest_local_dicom_metadata.py
```

The ingestion is idempotent for `ImagingStudy`, `ImagingSeries`, and
`ImagingInstance`. It also creates or updates one `LocalDicomFile` registry
record per ingested instance. Each registry row links an `ImagingInstance` to a
repository-relative local file path, SHA-256 checksum, file size, and
availability flag. Absolute paths are not stored, and local file paths are not
exposed through the public metadata API.

The ingestion reads DICOM headers only with `pydicom stop_before_pixels=True`.
The registry exists so later local-only scientific operations can select real
DICOM files through PostgreSQL before explicitly loading pixel data.

## Local DB-Selected Pixel Loading

After validation and ingestion, the private local loader can select one
`ImagingSeries` and `ImagingInstance` through PostgreSQL, resolve the linked
`LocalDicomFile`, and explicitly read `pydicom` `pixel_array` into a NumPy
array. This is a local scientific-processing layer, not a public raw-DICOM API.
Raw pixel arrays and local file paths are not exposed by the existing public API
endpoints.

CT middle slice:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/load_dicom_pixels_from_db.py \
  --series-instance-uid 1.3.6.1.4.1.14519.5.2.1.133320994602881796006698916833783151254
```

PT middle slice:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/load_dicom_pixels_from_db.py \
  --series-instance-uid 1.3.6.1.4.1.14519.5.2.1.246352124462042526540512717085218914533
```

This step does not download data, does not call external services, does not run
SciPy operations, and does not generate PNG visualizations. NumPy/SciPy
operations and visualization will be implemented in later steps.

## One-Command Local Backend Demo

After the selected DICOM subset has already been downloaded locally, run the
reviewer demo pipeline from the repository root:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/run_local_demo_pipeline.py
```

The pipeline validates local checksums and DICOM headers, ingests metadata into
PostgreSQL, runs the metadata-only geometry summary, and prints final database
counts. It does not download data, call external services, read pixel arrays, or
perform image analysis.

Optional flags can skip individual steps:

```sh
python scripts/run_local_demo_pipeline.py --skip-validation
python scripts/run_local_demo_pipeline.py --skip-ingestion
python scripts/run_local_demo_pipeline.py --skip-analysis
```

## Run The API Server

```sh
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py runserver --settings=config.settings.development
```

Open:

```text
http://localhost:8000/api/v1/overview/
```

See [api_usage.md](api_usage.md) for endpoint examples.

## Run The Frontend Dashboard

The dashboard is a Vite, React, and TypeScript app that reads metadata from the
backend API. Start it from a second shell after the backend server is running:

```sh
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173/
```

The frontend uses `VITE_API_BASE_URL` when set and defaults to
`http://localhost:8000`. It displays overview counts, imaging series metadata,
and stored quantitative analysis results. It does not download DICOM data, read
pixel arrays, or perform image diagnosis.

## Metadata-Only Geometry Summary

Run the first quantitative metadata summary after ingestion:

```sh
POSTGRES_PASSWORD=qmip_dev_password python scripts/run_series_geometry_summary.py
```

This command reads PostgreSQL metadata only. It does not read DICOM files or
pixel arrays.

Stored analysis runs and measurement results are available through:

```text
http://localhost:8000/api/v1/analysis/runs/
http://localhost:8000/api/v1/analysis/results/
```

## Tests And Quality Checks

Run tests from the repository root:

```sh
POSTGRES_PASSWORD=qmip_dev_password pytest
```

Run checks from `backend/`:

```sh
python manage.py check --settings=config.settings.development
python manage.py check --settings=config.settings.test
ruff check .
mypy .
```

The test suite creates ORM records directly and does not require local raw DICOM
files.
