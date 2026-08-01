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

Only collection-level candidate information is recorded at this stage. Study,
series, instance, file-path, and checksum fields remain placeholders until they
are verified from real source metadata.

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

The next future step is to query source metadata and choose a tiny subset, for
example 1 subject, 1 study, and 1-2 series. Exact file counts for that subset
will be known only after the source metadata is queried.
