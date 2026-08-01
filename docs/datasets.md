# Dataset Selection

The first real public deidentified imaging dataset for this project has not
been selected yet.

The initial documentation layer lives in `backend/tests/real_data/`. It is a
manifest contract for a future small subset of real public deidentified imaging
data. It does not store raw DICOM files, synthetic DICOM files, patient records,
fake medical metadata, ingestion logic, API endpoints, frontend code, or
algorithms.

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

Until a real dataset is selected, the manifest files must remain placeholder
templates.
