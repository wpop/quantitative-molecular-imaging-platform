# Dataset Selection

The first candidate real public deidentified imaging dataset for this project
has been selected for review: `CT-vs-PET-Ventilation-Imaging`.

The initial documentation layer lives in `backend/tests/real_data/`. It is a
manifest contract for a future small subset of real public deidentified imaging
data. It does not store raw DICOM files, synthetic DICOM files, patient records,
fake medical metadata, ingestion logic, API endpoints, frontend code, or
algorithms.

This step downloads 0 files. Raw DICOM files are not stored in Git.

## First Candidate

`CT-vs-PET-Ventilation-Imaging` is the first candidate because it is a public,
complete lung cancer imaging collection available through The Cancer Imaging
Archive (TCIA) and Imaging Data Commons (IDC). It has DOI
`10.7937/3ppx-7s22`, license `CC BY 4.0`, disease area `lung cancer`, primary
site `lung`, species `human`, and modalities `CT`, `PT`, and `RWV`.

The full collection contains 20 subjects, 22 studies, 119 series, and 29,491
DICOM images/files. Its full size is 14.93 GB, so the project will not download
the full collection for tests.

Collection-level candidate information and a metadata-only tiny subset are
recorded at this stage. Raw DICOM image data, SOP instance lists, local file
paths, and checksums remain absent or placeholders until a later verification
step.

## Step 4 Metadata Query

Step 4 queries metadata only. The project uses public TCIA/NBIA metadata APIs
first to inspect patient, study, series, and series-size records for the
candidate collection. This step does not call image download endpoints and does
not download DICOM files.

The metadata query is used to select only a tiny real subset for later review:
one subject, one study, and one or two series. Full dataset download is not
allowed for tests. Exact DICOM file counts for the selected subset are known
only after source metadata is queried.

## Step 5 Local Selected Series Download

Step 5 downloads only the selected CT and PT series for subject `CT-PET-VI-01`.
The expected local subset size is about 574 MB across 1,149 DICOM objects. This
is acceptable for optional local validation, but raw DICOM files must not be
stored in Git or required by CI.

Future CI should use metadata-only checks or optional local-data tests. Full
dataset download remains forbidden for tests.

## Step 6 Local DICOM Validation

Step 6 validates the optional local selected DICOM subset without downloading
data. It checks SHA-256 checksums, `StudyInstanceUID`, `SeriesInstanceUID`,
`Modality`, and expected file counts for the selected CT and PT series.

This validation reads DICOM headers only. It does not perform image analysis or
load pixel arrays.

## Step 7 Local Metadata Ingestion

Step 7 ingests validated local DICOM headers into PostgreSQL through the Django
ORM. It does not download data and does not read pixel data.

The expected result for the selected subset is 1 `ImagingStudy`, 2
`ImagingSeries` records, and 1,149 `ImagingInstance` records.

## Step 8 Read-Only Metadata API

Step 8 exposes ingested PostgreSQL metadata through read-only REST API
endpoints. The API is metadata-only: it does not read raw DICOM files, does not
read pixel data, and does not expose pixel data.

## Step 9 Metadata Overview Endpoint

Step 9 adds a read-only overview endpoint that summarizes already ingested
PostgreSQL metadata for future dashboard use. The endpoint does not read DICOM
files and does not expose pixel data.

## Selection Criteria

A candidate dataset should meet all of the following criteria:

- Public or research-accessible through documented terms.
- Deidentified by the source provider.
- Imaging metadata available from the source.
- Small enough to support focused tests without storing raw data in Git.
- Preferably distributed as DICOM.
- Suitable for a quantitative imaging workflow.

## Selection Process

1. Identify candidate public or research-accessible imaging datasets.
2. Review license, citation, attribution, and access requirements.
3. Confirm the source describes the data as deidentified.
4. Select a minimal number of studies and series that exercise the intended
   quantitative imaging workflow.
5. Record the selected dataset, studies, series, and expected files in
   `backend/tests/real_data/selected_studies.yaml`.
6. Mirror the finalized selection in
   `backend/tests/real_data/dataset_manifest.json` for future machine checks.
7. Store SHA-256 checksums in `backend/tests/real_data/checksums.sha256` only
   after real files have been downloaded outside Git.

After metadata query, the next future step is to review the tiny subset and
decide whether any raw DICOM files should be downloaded outside Git for a
separate validation fixture.
