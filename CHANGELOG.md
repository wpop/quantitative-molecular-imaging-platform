# Changelog

All notable changes to Quantitative Molecular Imaging Platform are documented
in this file.

The format follows the spirit of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
uses semantic versioning for release labels.

## Unreleased

- No unreleased changes are documented yet.

## 0.2.0 - 2026-08-02

### Added

- Selected public deidentified TCIA PET/CT local workflow for portfolio and
  research review.
- PostgreSQL imaging metadata models, ingestion records, and database-backed
  tracking for studies, series, instances, ingestion jobs, and analysis
  metadata.
- `LocalDicomFile` registry for repository-relative local DICOM file records.
- Database-selected DICOM pixel loading for local scientific processing.
- CT rescaling to Hounsfield Units (`HU`).
- PT rescaling reported as `rescaled_pixel_value`, without SUV claims.
- SciPy Gaussian filtering with configurable positive sigma.
- Sobel gradient-magnitude operation.
- Matplotlib PNG visualization artifact generation.
- `VisualizationArtifact` PostgreSQL registry for generated PNG metadata.
- Read-only artifact metadata API and registered PNG image API.
- Controlled visualization-generation API that accepts scientific parameters
  without accepting DICOM or output paths.
- React/TypeScript visualization workbench with registered artifact display.
- Frontend generation controls for supported operations and display parameters.
- Artifact filtering, selection, refresh, and deduplication behavior in the
  workbench.
- Portfolio screenshot, architecture documentation, and focused demo guide.

### Changed

- Documentation now presents the repository as a v0.2.0 local quantitative
  molecular imaging portfolio project.
- README navigation now links to the changelog, architecture documentation,
  local workflow, API usage, and v0.2.0 release notes.

### Security

- Public API responses do not expose local filesystem paths.
- Clients cannot submit DICOM paths, output paths, artifact paths, image bytes,
  or NumPy arrays.
- PNG bytes and NumPy arrays are not stored in PostgreSQL.
- The project remains explicitly non-clinical research and portfolio software.

### Validation

- 157 backend tests passed.
- 23 frontend tests passed.
- mypy passed for 79 source files.
- Ruff passed.
- TypeScript typecheck passed.
- Vite production build passed.
- npm production audit found 0 vulnerabilities.
- Complete npm audit found 0 vulnerabilities.
- Real CT Gaussian generation passed.
- Real PT rescale generation passed.
- PNG SHA-256 verification passed.
- Artifact idempotency and deduplication passed.
