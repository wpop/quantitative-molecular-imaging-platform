# Local Orthanc Service

Orthanc provides a local research PACS service for this project. It is used as a
development dependency for future backend ingestion workflows that need to read
deidentified DICOM studies through Orthanc HTTP and DICOMweb interfaces.

This configuration is for local research and portfolio development only. It is
not a production PACS configuration and does not make any clinical security
claims.

Only public, deidentified datasets should be imported. Real downloaded medical
imaging files and generated derived outputs must not be committed to Git.

Local endpoints:

- Orthanc HTTP UI and REST API: `http://localhost:8042`
- DICOM listener: `localhost:4242`
- DICOMweb root: `http://localhost:8042/dicom-web/`
- Local username: `qmip`
- Local password: `qmip_orthanc_dev_password`

The backend will use this service later for ingestion integration. This step
only provides local service configuration; it does not add ingestion endpoints,
models, dataset download logic, or scientific algorithms.
