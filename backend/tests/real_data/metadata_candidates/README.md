# Metadata Candidates

This directory stores small real metadata snapshots used to choose a tiny
public deidentified imaging subset for tests.

Raw DICOM images are not stored here. This directory must not contain DICOM
pixel data, full collection downloads, synthetic DICOM files, fake patient
records, or invented medical metadata.

The metadata snapshots are used only to choose a tiny subset, such as one
subject, one study, and one or two series. Full collection download is forbidden
for tests.

Exact DICOM file counts for the chosen subset are determined from source
metadata before any future download. Any future raw DICOM files must remain
outside Git.
