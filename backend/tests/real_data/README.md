# Real Data Test References

This directory is reserved for references to a small, selected subset of real
public deidentified imaging data that may be used by future integration or
validation tests.

It must contain references and manifest metadata only. Raw DICOM files, derived
medical images, patient records, and private health information must not be
stored in Git.

The files in this directory define the documentation layer for future real-data
test fixtures:

- `selected_studies.yaml` is the human-readable selection worksheet. It records
  the candidate public dataset under review and, later, the verified studies
  and series selected from source metadata.
- `dataset_manifest.json` is the machine-readable manifest contract. Future
  tools can use it to confirm the selected dataset identity, expected files,
  checksums, and ingestion expectations.
- `checksums.sha256` is the checksum list for downloaded DICOM files that are
  kept outside Git. It remains placeholder-only until real files are available
  locally.

The first candidate dataset has been selected for review:
`CT-vs-PET-Ventilation-Imaging`, available through The Cancer Imaging Archive
(TCIA) and Imaging Data Commons (IDC).

No DICOM files are downloaded in this step. Study-level, series-level,
instance-level, file-path, and checksum fields remain placeholders until they
are verified from real source metadata in a later step.

## Local Selected DICOM Subset

The selected CT and PT DICOM series may be downloaded locally for validation
with `scripts/download_tcia_selected_series.py`. Raw DICOM files remain outside
Git under `datasets/raw/`.

The `checksums.sha256` file may contain SHA-256 checksums for the local selected
subset after that download. The full collection must not be downloaded for
tests.

## Local DICOM Validation

The optional local subset can be validated with
`scripts/validate_local_dicom_subset.py`. The validator checks SHA-256
checksums and DICOM headers for the selected CT and PT series under
`datasets/raw/`.

Validation reads metadata only and does not analyze pixel data. It requires the
optional local DICOM files to exist outside Git under `datasets/raw/`.

## Local Metadata Ingestion

Validated local DICOM metadata can be ingested into the Django domain models
with `scripts/ingest_local_dicom_metadata.py`. The ingestion reads DICOM
headers only and does not read pixel arrays.

Raw DICOM files remain outside Git under `datasets/raw/`. The ingestion is
idempotent for `ImagingStudy`, `ImagingSeries`, and `ImagingInstance` records.
