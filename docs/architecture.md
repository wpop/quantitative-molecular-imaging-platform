# Architecture

Quantitative Molecular Imaging Platform v0.1 is a research software workflow
for a small selected public deidentified PET/CT subset. The system is designed
to show safe medical imaging data handling, PostgreSQL-backed metadata modeling,
read-only APIs, and a small reviewer-friendly dashboard.

## System Overview

```mermaid
flowchart LR
    A[Real public TCIA PET/CT subset] --> B[Local DICOM files ignored by Git]
    B --> C[Validation script]
    C --> D[Ingestion script]
    D --> E[(PostgreSQL metadata)]
    E --> F[Geometry summary analysis]
    E --> I[DB-selected local pixel loader]
    I --> J[NumPy array for local scientific work]
    E --> G[Read-only DRF API]
    F --> G
    G --> H[React dashboard]
```

The raw selected DICOM subset is optional and local-only. It is stored under
`datasets/raw/`, which is ignored by Git. The durable project artifacts are the
manifest documentation, metadata validation scripts, ingestion scripts, Django
models, API endpoints, and frontend dashboard.

## Backend Components

- `apps.imaging` stores study, series, and instance metadata.
- `apps.imaging.LocalDicomFile` maps one ingested `ImagingInstance` to one
  repository-relative local DICOM file.
- `apps.ingestion` stores ingestion job and event metadata.
- `apps.analysis` stores analysis runs and measurement results.
- `apps.analysis.imaging_io` selects local DICOM instances through PostgreSQL,
  resolves `LocalDicomFile` records, and explicitly loads `pixel_array` for
  local scientific processing.
- `config.urls` exposes read-only API routes under `/api/v1/`.
- `config.cors` allows only configured development frontend origins to read the
  API during local dashboard development.

The backend API reads PostgreSQL metadata only. It does not read raw DICOM
files, does not expose DICOM pixel data, and does not perform image diagnosis.
Local DICOM registry paths are not exposed through the public metadata API.
The pixel-loading service is a private local processing layer, not a public
raw-DICOM or pixel API.

## Data Flow

1. A selected public TCIA PET/CT subset can be downloaded locally for optional
   validation.
2. `scripts/validate_local_dicom_subset.py` verifies checksums and DICOM
   headers without reading pixel arrays.
3. `scripts/ingest_local_dicom_metadata.py` reads DICOM headers with
   `pydicom stop_before_pixels=True`, upserts imaging metadata, and creates
   `LocalDicomFile` records for repository-relative local file access.
4. `scripts/run_series_geometry_summary.py` reads PostgreSQL metadata and
   creates a minimal geometry summary as analysis metadata.
5. `scripts/load_dicom_pixels_from_db.py` selects an `ImagingSeries` and
   `ImagingInstance` through PostgreSQL, resolves the linked `LocalDicomFile`,
   and explicitly reads `pydicom` `pixel_array` into a NumPy array.
6. Read-only DRF endpoints expose overview, imaging, ingestion, and analysis
   metadata.
7. The React dashboard fetches the API responses and displays a compact
   metadata summary.

## Frontend Role

The frontend is intentionally small. It proves that the backend APIs are usable
from a browser-based dashboard and displays:

- Overview counts.
- Modalities and latest ingestion status.
- Imaging series metadata.
- Stored quantitative measurement metadata.

It does not load raw DICOM files, does not display pixel data, does not upload
files, and does not run analysis in the browser.

## Safety Boundaries

- Raw DICOM files are ignored by Git and remain local-only.
- Local DICOM registry records store repository-relative paths only. Absolute
  paths are rejected.
- Local file paths are not exposed through the public metadata API.
- No fake patient records or synthetic DICOM files are created.
- No pixel arrays are read by ingestion or validation scripts.
- Pixel arrays are read only by the private local DB-selected loader.
- The API and frontend expose metadata only.
- The geometry summary is derived from already ingested metadata.
- The project is not intended for diagnosis, treatment decisions, or production
  patient care.

## Intentionally Out Of Scope For v0.1

- Clinical deployment readiness.
- Authentication and authorization.
- Upload workflows.
- SQL explorer or query-builder UI.
- DICOM pixel visualization.
- Image analysis algorithms.
- Large dataset processing.
- CI workflows that require local raw DICOM data.

## Future Scientific Operations

The `LocalDicomFile` registry is the bridge for scientific operations:
PostgreSQL selects specific real DICOM instances, then local-only workers
resolve repository-relative paths and explicitly load pixel data. NumPy/SciPy
operations, CT windowing, Hounsfield Unit conversion, and visualization are
intentionally left for later steps.
