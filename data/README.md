# Data Sources

All raw data is gitignored. Acquire each source and place in the
corresponding data/raw/ subfolder before running the pipeline.

## parcels/
- Source: Maricopa County Assessor GIS
- File: Parcels_All.shp
- Acquired: March 2026

## assessor/
- Source: Maricopa County Assessor Tax Roll
- Files: Secured_Master_*.txt
- Acquired: March 2026
- Encoding: cp1252 | Delimiter: pipe

## zoning/
- Source: City of Phoenix Open Data
- Acquired: March 2026
- ...

## transit/
- Source: Valley Metro GTFS
- ...

## census/
- Source: NHGIS (nhgis.org)
- ACS 2019–2023 5-year estimates, tract level
- Acquired: November 2025
- File: nhgis0005_ds267_20235_tract_E.csv

## jobs/
- Source: U.S. Census LODES WAC
- File: az_wac_S000_JT00_2022.csv
- Acquired: March 2025
- Geography: AZ block groups (AZ_blck_grp_2023.shp)