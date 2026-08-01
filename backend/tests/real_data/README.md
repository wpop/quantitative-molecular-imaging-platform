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
  which public dataset, studies, and series are intended for use once a real
  source has been chosen.
- `dataset_manifest.json` is the machine-readable manifest contract. Future
  tools can use it to confirm the selected dataset identity, expected files,
  checksums, and ingestion expectations.
- `checksums.sha256` is the checksum list for downloaded DICOM files that are
  kept outside Git. It remains placeholder-only until real files are available
  locally.

The first real public dataset has not been selected yet. Until then, every value
in these files is intentionally marked as a placeholder.
