# Demo Guide

This guide walks through the local portfolio demonstration for the React
scientific workbench and registered visualization artifacts.

## Prerequisites

- PostgreSQL is running.
- The development database is configured and migrated.
- The selected public deidentified TCIA PET/CT dataset has already been
  ingested.
- `LocalDicomFile` records are available for the selected CT and PT series.
- Python backend dependencies and frontend dependencies are installed.

No private absolute filesystem paths are required in the browser.

## Start Django

From the repository root:

```sh
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py runserver 127.0.0.1:8000 --noreload --settings=config.settings.development
```

Leave this process running.

## Start Vite

In a second shell:

```sh
cd frontend
npm run dev
```

Leave this process running.

## Open The Application

Open:

```text
http://localhost:5173
```

The dashboard defaults to `http://localhost:8000` for the backend API unless
`VITE_API_BASE_URL` is set.

## CT Gaussian Demonstration

In the Generate Visualization section, enter:

```text
Series Instance UID:
1.3.6.1.4.1.14519.5.2.1.133320994602881796006698916833783151254

Operation:
gaussian

Gaussian sigma:
1.5

Window center:
-600

Window width:
1500
```

Submit the form. The expected result is:

- A successful generation message.
- A CT Gaussian artifact selected in the artifact list.
- A PNG displayed in the workbench.
- Hounsfield Unit (`HU`) metadata displayed.
- Registered artifact metadata shown for the selected PNG.

## PT Rescale Demonstration

In the Generate Visualization section, enter:

```text
Series Instance UID:
1.3.6.1.4.1.14519.5.2.1.246352124462042526540512717085218914533

Operation:
rescale
```

Submit the form. The expected result is:

- A PT artifact selected in the artifact list.
- A PNG displayed in the workbench.
- Value units shown as `rescaled_pixel_value`.
- No SUV claim.

## Filtering And Metadata Review

Use the artifact filters to narrow registered artifacts by supported metadata
fields such as series UID, SOP UID, operation, or modality. Selecting an
artifact updates the PNG display and the registered metadata panel.

Verify that the displayed metadata matches the selected artifact, including
operation, modality, units, slice index, dimensions, display range, checksum,
study UID, series UID, and SOP UID.

## Expected HTTP Flow

The browser uses the API through registered metadata and image URLs:

```text
POST /api/v1/analysis/artifacts/generate/
GET /api/v1/analysis/artifacts/
GET /api/v1/analysis/artifacts/{id}/image/
```

The browser does not send local DICOM paths, PNG paths, image bytes, or NumPy
arrays.

## Troubleshooting

- HTTP 404 after generation usually means the Series Instance UID is incomplete
  or does not match an ingested series.
- If the API cannot connect to the database, confirm PostgreSQL is running and
  the development database has been migrated.
- If the frontend shows API errors, confirm Django is still running on
  `127.0.0.1:8000`.
- If the frontend cannot reach port 8000, check the backend server URL and any
  `VITE_API_BASE_URL` override.
- If generation reports that the requested imaging series could not be
  selected, confirm `LocalDicomFile` records exist for the ingested series.
- If a registered local DICOM file is unavailable, rerun the local validation
  and ingestion workflow after restoring the selected DICOM files.
- If a generated PNG is unavailable, regenerate the artifact from the
  workbench so the backend can render and register a fresh PNG.
