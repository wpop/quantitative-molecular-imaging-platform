# API Usage

The backend exposes read-only, metadata-only REST API endpoints through Django
REST Framework. The API reads PostgreSQL metadata only. It does not read raw
DICOM files, expose DICOM pixel data, or perform image analysis.

## Run The Development Server

Start local services and apply migrations before running the server:

```sh
make services-up
cd backend
POSTGRES_PASSWORD=qmip_dev_password python manage.py migrate --settings=config.settings.development
POSTGRES_PASSWORD=qmip_dev_password python manage.py runserver --settings=config.settings.development
```

The local API base URL is:

```text
http://localhost:8000/api/v1/
```

## Endpoints

- `GET /api/v1/overview/`
- `GET /api/v1/imaging/studies/`
- `GET /api/v1/imaging/series/`
- `GET /api/v1/imaging/instances/`
- `GET /api/v1/ingestion/jobs/`
- `GET /api/v1/ingestion/events/`

Write methods such as `POST`, `PUT`, `PATCH`, and `DELETE` are not supported
for these metadata endpoints.

## Overview Example

```sh
curl http://localhost:8000/api/v1/overview/
```

Example response from the known local development subset:

```json
{
  "studies_count": 1,
  "series_count": 2,
  "instances_count": 1149,
  "modalities": ["CT", "PT"],
  "source_datasets": ["CT-vs-PET-Ventilation-Imaging"],
  "source_subjects": ["CT-PET-VI-01"],
  "ingestion_jobs_count": 1,
  "latest_ingestion_status": "completed",
  "latest_ingestion_started_at": "2026-08-01T20:42:52.832853Z",
  "latest_ingestion_completed_at": "2026-08-01T20:42:54.077090Z"
}
```

## Imaging Metadata

```sh
curl http://localhost:8000/api/v1/imaging/studies/
curl http://localhost:8000/api/v1/imaging/series/
curl http://localhost:8000/api/v1/imaging/instances/
```

Useful query parameters:

```sh
curl "http://localhost:8000/api/v1/imaging/studies/?source_dataset=CT-vs-PET-Ventilation-Imaging"
curl "http://localhost:8000/api/v1/imaging/studies/?source_subject_id=CT-PET-VI-01"
curl "http://localhost:8000/api/v1/imaging/series/?modality=CT"
curl "http://localhost:8000/api/v1/imaging/series/?study_instance_uid=1.3.6.1.4.1.14519.5.2.1.297577087050970310787702792940607009472"
curl "http://localhost:8000/api/v1/imaging/instances/?series_instance_uid=1.3.6.1.4.1.14519.5.2.1.133320994602881796006698916833783151254"
```

Supported imaging filters:

- `study_instance_uid`
- `series_instance_uid`
- `modality`
- `source_dataset`
- `source_subject_id`

## Ingestion Metadata

```sh
curl http://localhost:8000/api/v1/ingestion/jobs/
curl http://localhost:8000/api/v1/ingestion/events/
```

Useful query parameters:

```sh
curl "http://localhost:8000/api/v1/ingestion/jobs/?status=completed"
curl "http://localhost:8000/api/v1/ingestion/jobs/?source_type=local_manifest"
curl "http://localhost:8000/api/v1/ingestion/events/?level=info"
```

The ingestion API exposes job and event metadata only. It does not expose raw
file contents or local raw DICOM paths.
