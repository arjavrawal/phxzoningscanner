from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", str(PROJECT_ROOT / "database" / "scanner.duckdb")))
DATA_DIR     = PROJECT_ROOT / "data"
ZONING_DIR   = DATA_DIR / "raw" / "zoning"
CONTEXT_DIR  = DATA_DIR / "raw" / "context"

VILLAGES_SHP  = ZONING_DIR / "Villages" / "Villages.shp"
TOD_SHP       = ZONING_DIR / "Walkable_Urban_Code" / "Walkable_Urban_Code.shp"

CITY_LIMITS_SHP  = CONTEXT_DIR / "city_limits"
DPI_SHP          = CONTEXT_DIR / "dpi_service_area"
LIGHT_RAIL_SHP   = CONTEXT_DIR / "light_rail"
STREETS_SHP      = CONTEXT_DIR / "street_centerlines"
PARKS_SHP        = CONTEXT_DIR / "parks"

ARTERIAL_CLASSES = ("MA", "AT")

BASEMAP_URL         = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
BASEMAP_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    ' &copy; <a href="https://carto.com/">CARTO</a>'
)
MAP_CENTER          = [33.4484, -112.0740]
MAP_ZOOM            = 11
CHOROPLETH_MIN_LAT_SPAN = 0.15   # degrees; above this = too zoomed out for parcels
MAX_PARCELS_IN_VIEW     = 2000

COLOR_MMH           = "#00E5FF"
COLOR_UNDERUTILIZED = "#FF9800"
COLOR_SEC711        = "#69F0AE"
COLOR_TOD           = "#B39DDB"
COLOR_NEUTRAL       = "#4A4A6A"
COLOR_POLYGON       = "#FFEB3B"

SIDEBAR_BG   = "#1A1A2E"
CARD_BG      = "#16213E"
ACCENT       = "#0F3460"
TEXT_PRIMARY = "#E0E0E0"
TEXT_MUTED   = "#9E9E9E"

ANALYSIS_LAYERS = [
    {"label": "MMH Feasible",    "value": "mmh",   "color": COLOR_MMH},
    {"label": "Underutilized",   "value": "under", "color": COLOR_UNDERUTILIZED},
    {"label": "§711 Candidates", "value": "s711",  "color": COLOR_SEC711},
    {"label": "In TOD District", "value": "tod",   "color": COLOR_TOD},
    {"label": "None",            "value": "none",  "color": COLOR_NEUTRAL},
]

LAYER_CONDITIONS = {
    "mmh":   "mmh_feasibility_flag = TRUE",
    "under": "is_underutilized = TRUE",
    "s711":  "sec711_candidate_flag = TRUE",
    "tod":   "in_tod_district = TRUE",
    "none":  "1=1",
}

CONTEXT_LAYERS = [
    {"label": "Urban Villages",   "value": "villages",   "color": "#7B8CDE"},
    {"label": "Zoning",           "value": "zoning",     "color": "#FF6B6B"},
    {"label": "Light Rail",       "value": "lightrail",  "color": "#FFD700"},
    {"label": "City Limits",      "value": "citylimits", "color": "#FFFFFF"},
    {"label": "DPI Service Area", "value": "dpi",        "color": "#69F0AE"},
    {"label": "Arterial Streets", "value": "arterials",  "color": "#FF9800"},
    {"label": "Parks",            "value": "parks",      "color": "#4CAF50"},
]

METRICS = {
    "overview": [
        ("Total Parcels",     "total_parcels",        "{:,.0f}",  "Non-exempt parcels in area"),
        ("Total Acreage",     "total_acreage",        "{:,.1f}",  "Gross acres"),
        ("MMH Feasible",      "mmh_feasible_parcels", "{:,.0f}",  "Parcels eligible for MH Overlay"),
        ("Underutilized",     "underutilized_parcels","{:,.0f}",  "Improvement/land ratio < 0.5"),
        ("§711 Candidates",   "sec711_candidates",    "{:,.0f}",  "Commercial conversion eligible"),
        ("Vacant Parcels",    "vacant_parcels",       "{:,.0f}",  "No units & building < 200 sqft"),
    ],
    "housing": [
        ("Units / Acre",      "units_per_acre",            "{:.2f}",  "Actual residential density"),
        ("Households / Acre", "households_per_acre",       "{:.2f}",  "ACS 2023 (areal interpolation)"),
        ("Total Units",       "total_units",               "{:,.0f}", "Assessor units + SFR zone proxy"),
        ("Zoning Capacity",   "total_permitted_capacity",  "{:,.0f}", "Max DUs under current zoning"),
        ("Upzoning Gap",      "total_upzoning_gap",        "{:,.0f}", "Permitted minus existing DUs"),
        ("MMH Feasible",      "mmh_feasible_parcels",      "{:,.0f}", "Parcels eligible for MH Overlay"),
    ],
    "fiscal": [
        ("LPV / Acre",        "lpv_per_acre",          "${:,.0f}", "Taxable limited property value"),
        ("FCV / Acre",        "fcv_per_acre",          "${:,.0f}", "Full cash value per acre"),
        ("Total LPV",         "total_lpv",             "${:,.0f}", "Total taxable value"),
        ("Total FCV",         "total_fcv",             "${:,.0f}", "Total assessed market value"),
        ("Median HH Income",  "avg_median_hh_income",  "${:,.0f}", "Parcel-weighted avg of tract medians (ACS 2023)"),
        ("Median Gross Rent", "avg_median_gross_rent", "${:,.0f}", "Parcel-weighted avg of tract medians (ACS 2023)"),
    ],
    "economic": [
        ("Jobs / Acre",         "jobs_per_acre",         "{:.2f}",  "LODES 2023 apportioned jobs"),
        ("Total Jobs",          "total_jobs",            "{:,.0f}", "Apportioned workplace jobs"),
        ("Households / Acre",   "households_per_acre",   "{:.2f}",  "ACS 2023 (areal interpolation)"),
        ("Street Miles / Acre", "street_miles_per_acre", "{:.3f}",  "All street centerlines / gross acres"),
    ],
}

MODE_SHARE_FIELDS = [
    ("Drove Alone",       "drove_alone_share",  "#EF5350"),
    ("Carpooled",         "carpool_share",      "#FF9800"),
    ("Transit",           "transit_mode_share", "#00E5FF"),
    ("Walked",            "walk_share",         "#69F0AE"),
    ("Worked from Home",  "wfh_share",          "#B39DDB"),
    ("Other",             "other_share",        "#9E9E9E"),
]