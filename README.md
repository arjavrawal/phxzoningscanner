# Phoenix Zoning Scanner

A parcel-level analytical tool identifying where missing middle housing (MMH) is feasible, but legally prohibited, across the City of Phoenix.

**Author:** Arjav Rawal
**Course:** GIS 322 (Programming Principles in GIS II), Spring 2026, Arizona State University
**Instructor:** Dr. Debayan Mandal

---

## Live application

Link TBC

*The application landing screen shows the citywide summary; selecting an Urban Village or drawing a polygon recomputes the scorecard for that area.*

---

## Project summary

Arizona's "missing middle" housing law took effect in January 2026. It requires every city over 75,000 residents to legalize the construction of duplexes, triplexes, fourplexes, and townhomes within at least one mile of the city’s central business district.

Phoenix passed its compliance ordinance in November 2025, and a follow-up bill currently moving through the 2026 legislative session would exempt historic neighborhoods from that requirement.

The debate has been driven largely by emotion, and the empirical question that should be driving it - which parcels are actually affected, and where - has not been answered at this granular of a resolution.

That is what the Phoenix Zoning Scanner aims to do. For any drawn polygon or pre-defined geography, the tool counts parcels eligible for the Missing Housing Overlay, parcels currently underutilized, parcels in TOD districts, and §711 conversion candidates, alongside an interactive scorecard showing housing, fiscal, and economic characteristics.

---

## Features

- Interactive parcel-level map covering City of Phoenix parcels
- Polygon-draw tool: draw any boundary and receive a real-time scorecard
- Pre-defined geography selector: Urban Villages and TOD districts
- Four toggleable analysis layers: MMH-feasible, underutilized, §711 conversion candidates, TOD
- Toggleable context layers: zoning, light rail, urban villages, parks, arterials, Downtown Phoenix, city limits
- Four-tab scorecard: Overview, Housing, Fiscal, Economic
- **In-progress:** Per-parcel detail modal with overlay parsing (HP, TOD, height waivers, pending cases)

---

## Methodology

The **MMH-feasibility flag** combines six conditions:

1. The base zone is on Phoenix's §632.C eligibility list for the Missing Housing Overlay (residential SF and low-density MF base districts)
2. The base zone does not already permit multi-family by-right (the MH Overlay is meaningful only as a meaningful upzoning)
3. The parcel is not tax-exempt
4. The parcel is not in a Historic Preservation overlay district
5. The parcel is not in the Deer Valley Airport Overlay
6. The parcel is not a Maricopa County island parcel

The **underutilization flag** is set when the improvement-to-land value ratio is below 0.5.

The **§711 candidate flag** identifies parcels eligible for Phoenix's multifamily conversion provision, which permits conversion of obsolete commercial buildings without rezoning.

For full methodology, including derivations and data sources for each metric, see the written project report.

### Known limitations

- **Downtown Code (DTC) density is NULL** - derived from §1202.C regulating maps that exist as image-based GIS layers, not parsable HTML
- **§632.C.2.f geographic exclusions are not yet modeled** - AIO, AICUZ, freeway-proximity, Superfund, state-trust land. As a result the tool currently overstates MMH-feasibility in airport-adjacent and freeway-adjacent neighborhoods
- **Choropleth rendering offset** - the parcels render with a constant latitude offset due to a WKB-to-EPSG:4326 reprojection bug in the application layer; spatial filtering and computed metrics are unaffected

---

## Tech stack

| Layer | Technology |
|---|---|
| Database | DuckDB (with Spatial extension) |
| Pipeline | Python 3.11, GeoPandas, Shapely, pandas, numpy |
| Census/Geo | pygris, Census API |
| Application | Plotly Dash, dash-leaflet |
| Deployment | Hugging Face Spaces (Docker SDK), gunicorn |

---

## Repository structure

├── app/                          # Dash application code
│   ├── main.py                   # App entrypoint
│   ├── layout.py                 # Dash component layout
│   ├── callbacks.py              # Interactive callbacks
│   ├── queries.py                # DuckDB query layer
│   └── styles.py                 # Color and styling constants
├── pipeline/                     # Data pipeline scripts
│   ├── config.py                 # Path constants, column mappings
│   ├── 01_clean_parcels.py       # Geometry cleaning
│   ├── 02_enrich_assessor.py     # Assessor master joins
│   ├── 03_build_residential.py   # R116/R122 unit aggregation
│   ├── 04_join_zoning.py         # Spatial join + ordinance + WU integration
│   ├── 05_join_census_acs.py     # ACS data integration
│   ├── 06_build_lodes.py         # LODES jobs apportionment prep
│   ├── 07_build_scorecard.py     # Derived metrics + flags
│   ├── 08_load_duckdb.py         # Final database assembly
│   ├── wu_parser.py              # Custom WU transect zone-code parser
│   └── run_pipeline.py           # Orchestrator with --from / --only flags
├── notebooks/
│   └── encode_ordinance.ipynb    # Phoenix Zoning Ordinance encoder
├── data/                         # Gitignored — see Data Sources below
├── database/                     # scanner.duckdb generated here
├── docs/                         # Documentation, screenshots, diagrams
├── Dockerfile                    # Hugging Face Space build
├── requirements.txt              # Python dependencies
└── README.md

---

## Setup and run

### Prerequisites

- Python 3.11+
- Git LFS (for `scanner.duckdb` if cloning the deployed Space)
- ~5 GB disk space for raw data

### Install

```bash
# Clone the repository
git clone https://huggingface.co/spaces/sgsup-asu/phoenix-zoning-scanner
cd phxzoningscanner

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the application (uses pre-built database)

If `scanner.duckdb` is already present (it ships with the Hugging Face Space):

```bash
cd app
python main.py
```

The app will be available at `http://localhost:7860`.

### Rebuild the database from raw sources

**These steps are only listed for documentation purposes. Storage limits on HF Spaces' free tier prevent me from posting the entire pipeline in full.**

To regenerate `scanner.duckdb` from raw data, you'll need to acquire the source files (see Data Sources below). Then:

```bash
# Run the full pipeline
python pipeline/run_pipeline.py

# Or run from a specific step
python pipeline/run_pipeline.py --from 4

# Or run only a specific step
python pipeline/run_pipeline.py --only 7

# Re-encode the ordinance (regenerates zoning_district_standards.csv)
jupyter nbconvert --execute encode_ordinance.py --to notebook
```

The full pipeline takes approximately 15-20 minutes to complete from raw data on a modern laptop.

---

## Data sources

All raw data is gitignored. Acquire each source and place in the corresponding `data/raw/` subdirectory before running the pipeline.

| Subfolder | Source | License |
|---|---|---|
| `parcels/` | [Maricopa County Assessor GIS](https://gis.maricopa.gov/) — `Parcels_All.shp` | Public record |
| `assessor/` | [Maricopa County Assessor Tax Roll](https://mcassessor.maricopa.gov/) — Pipe-delimited cp1252 | Public record |
| `zoning/` | [City of Phoenix Open Data](https://www.phoenixopendata.com/) | CC-BY-style; attribution required |
| `census/` | [U.S. Census Bureau ACS 2019-2023 5-year](https://www.census.gov/data/developers/data-sets/acs-5year.html) | Public domain |
| `jobs/` | [U.S. Census LODES 2023](https://lehd.ces.census.gov/data/) — `az_wac_S000_JT00_2023.csv` | Public domain |
| `ordinance/` | [Phoenix Zoning Ordinance](https://codelibrary.amlegal.com/codes/phoenix/latest/overview) — HTML scrape | Public; municipal code |

**Raw files are not committed because of storage limitations.**

---

## License

Apache License 2.0 — see `LICENSE` file. This applies to original code only; data sources retain their respective licenses.

---

## AI Disclosure

Per the GIS 322 Gen AI Usage Policy:

I used Generative AI extensively throughout this project for the following purposes:

- **Code Review:** Portions of the Dash application callbacks were drafted with Claude's assistance. I reviewed, modified, and tested all generated code before integration.
- **CSS**: Claude was used to develop an initial sketch of the CSS file, which I then modified based on my preferences.
- **Debugging:** The Claude Code extension in VS Code was used to help debug portions of the app, including the Dash callbacks, the data-loading bug, and the WU transect parser.
- **Methodology Audit:** I asked Claude to perform a thorough audit of my zoning ordinance encoder; the audit surfaced bugs and methodological gaps which were addressed before final submission.
- **Documentation and Writing:** README structure.

All code was tested locally before deployment. All methodology decisions were made by me, based on my understanding of Phoenix land use policy. The connection to the policy debate, the choice of stakeholders and use cases, and the overall project conception are mine.
