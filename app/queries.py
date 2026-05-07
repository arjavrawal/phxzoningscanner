"""
queries.py — Phoenix Upzoning Scanner
All DuckDB query functions and geography boundary loading.
"""

import json
from functools import lru_cache
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping, shape
from shapely import wkb as shapely_wkb

from config import (
    DB_PATH, VILLAGES_SHP, TOD_SHP,
    CITY_LIMITS_SHP, DPI_SHP, LIGHT_RAIL_SHP, STREETS_SHP, PARKS_SHP,
    ZONING_DIR, ARTERIAL_CLASSES,
    LAYER_CONDITIONS, MAX_PARCELS_IN_VIEW,
    COLOR_MMH, COLOR_UNDERUTILIZED, COLOR_SEC711, COLOR_TOD, COLOR_NEUTRAL,
)

PROJECT_CRS = "EPSG:2868"


# ── Connection ────────────────────────────────────────────────────────────────

def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(DB_PATH))
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


# ── Geography boundaries ──────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_village_boundaries() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(VILLAGES_SHP)
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    name_col = next(
        (c for c in gdf.columns
         if c.upper() in ("NAME", "VILLAGENAME", "LABEL", "VILLAGE")),
        gdf.columns[0],
    )
    return gdf.rename(columns={name_col: "name"})[["name", "geometry"]].copy()


@lru_cache(maxsize=1)
def load_tod_boundaries() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(TOD_SHP)
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    name_col = next(
        (c for c in gdf.columns
         if c.upper() in ("APPLICABIL", "NAME", "LABEL")),
        gdf.columns[0],
    )
    return gdf.rename(columns={name_col: "name"})[["name", "geometry"]].copy()


def get_geography_options() -> list[dict]:
    options = [{"label": "— Select a geography —", "value": ""}]
    for name in sorted(load_village_boundaries()["name"].dropna().unique()):
        options.append({"label": f"🏙 {name}", "value": f"village::{name}"})
    for name in sorted(load_tod_boundaries()["name"].dropna().unique()):
        label = (name.replace("TOD District - ", "")
                     .replace("Extension Area", "Ext.")
                     .strip())
        options.append({"label": f"🚊 {label}", "value": f"tod::{name}"})
    return options


def get_geography_geojson(geo_value: str) -> dict | None:
    if not geo_value or "::" not in geo_value:
        return None
    geo_type, geo_name = geo_value.split("::", 1)
    gdf = load_village_boundaries() if geo_type == "village" else load_tod_boundaries()
    row = gdf[gdf["name"] == geo_name]
    if row.empty:
        return None
    return {
        "type": "Feature",
        "properties": {"name": geo_name},
        "geometry": mapping(row.geometry.iloc[0]),
    }


def get_geography_center_zoom(geo_value: str) -> tuple[list, int] | tuple[None, None]:
    feat = get_geography_geojson(geo_value)
    if not feat:
        return None, None
    geom  = shape(feat["geometry"])
    bounds = geom.bounds  # (minx=lon, miny=lat, maxx=lon, maxy=lat)
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    span   = max(bounds[3] - bounds[1], bounds[2] - bounds[0])
    if span > 0.2:    zoom = 11
    elif span > 0.1:  zoom = 12
    elif span > 0.05: zoom = 13
    else:             zoom = 14
    return center, zoom


# ── Polygon projection ────────────────────────────────────────────────────────

def geojson_feature_to_wkt_2868(feature: dict) -> str:
    geom = shape(feature["geometry"])
    gdf  = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326").to_crs(PROJECT_CRS)
    return gdf.geometry.iloc[0].wkt


# ── Zone code helpers ─────────────────────────────────────────────────────────

def get_all_zone_codes() -> list[dict]:
    con = _con()
    try:
        result = con.execute("""
            SELECT DISTINCT zone_code, zo_district_name
            FROM parcels
            WHERE zone_code IS NOT NULL
            ORDER BY zone_code
        """).fetchdf()
    finally:
        con.close()
    return [
        {"label": f"{r['zone_code']} — {r['zo_district_name'] or ''}",
         "value": r["zone_code"]}
        for _, r in result.iterrows()
    ]


def get_zone_codes_in_polygon(wkt_2868: str) -> list[dict]:
    con = _con()
    try:
        result = con.execute(f"""
            SELECT DISTINCT zone_code, zo_district_name
            FROM parcels
            WHERE ST_Within(geom, ST_GeomFromText('{wkt_2868}'))
              AND zone_code IS NOT NULL
              AND NOT COALESCE(is_exempt, FALSE)
            ORDER BY zone_code
        """).fetchdf()
    finally:
        con.close()
    return [
        {"label": f"{r['zone_code']} — {r['zo_district_name'] or ''}",
         "value": r["zone_code"]}
        for _, r in result.iterrows()
    ]


# ── Scorecard ─────────────────────────────────────────────────────────────────

def get_scorecard(wkt_2868: str) -> dict:
    where = (
        f"ST_Within(geom, ST_GeomFromText('{wkt_2868}')) "
        f"AND NOT COALESCE(is_exempt, FALSE) "
        f"AND NOT COALESCE(is_county_parcel, FALSE)"
    )
    con = _con()
    try:
        agg = con.execute(f"""
            SELECT
                COUNT(*)                                                      AS total_parcels,
                SUM(parcel_acreage)                                           AS total_acreage,
                SUM(lpv_amount)                                               AS total_lpv,
                SUM(full_cash_value)                                          AS total_fcv,
                SUM(COALESCE(units_actual_proxy, num_units, 0))               AS total_units,
                SUM(lodes_jobs_apportioned)                                   AS total_jobs,
                SUM(zoning_capacity_du)                                       AS total_permitted_capacity,
                SUM(upzoning_gap_du)                                          AS total_upzoning_gap,
                COUNT(*) FILTER (WHERE is_vacant)                             AS vacant_parcels,
                COUNT(*) FILTER (WHERE is_underutilized)                      AS underutilized_parcels,
                COUNT(*) FILTER (WHERE mmh_feasibility_flag)                  AS mmh_feasible_parcels,
                COUNT(*) FILTER (WHERE sec711_candidate_flag)                 AS sec711_candidates,
                SUM(lpv_amount)      / NULLIF(SUM(parcel_acreage), 0)        AS lpv_per_acre,
                SUM(full_cash_value) / NULLIF(SUM(parcel_acreage), 0)        AS fcv_per_acre,
                SUM(COALESCE(units_actual_proxy, num_units, 0))
                    / NULLIF(SUM(parcel_acreage), 0)                          AS units_per_acre,
                SUM(lodes_jobs_apportioned) / NULLIF(SUM(parcel_acreage), 0) AS jobs_per_acre,
                SUM(acs_transit_commuters)  / NULLIF(SUM(acs_total_commuters), 0) AS transit_mode_share,
                SUM(acs_drove_alone)    / NULLIF(SUM(acs_total_commuters), 0) AS drove_alone_share,
                SUM(acs_carpooled)      / NULLIF(SUM(acs_total_commuters), 0) AS carpool_share,
                SUM(acs_walked)         / NULLIF(SUM(acs_total_commuters), 0) AS walk_share,
                SUM(acs_other_means)    / NULLIF(SUM(acs_total_commuters), 0) AS other_share,
                SUM(acs_work_from_home) / NULLIF(SUM(acs_total_commuters), 0) AS wfh_share,
                SUM(acs_households * parcel_acreage / NULLIF(acs_tract_acreage, 0))
                    / NULLIF(SUM(parcel_acreage), 0)                          AS households_per_acre,
                SUM(acs_median_hh_income)  / NULLIF(COUNT(*), 0)             AS avg_median_hh_income,
                SUM(acs_median_gross_rent) / NULLIF(COUNT(*), 0)             AS avg_median_gross_rent
            FROM parcels
            WHERE {where}
        """).fetchdf()

        zone_df = con.execute(f"""
            SELECT
                zone_code,
                zo_district_name                                              AS district_name,
                COUNT(*)                                                      AS parcels,
                ROUND(SUM(parcel_acreage), 1)                                AS acreage,
                ROUND(SUM(parcel_acreage) * 100.0
                    / NULLIF(SUM(SUM(parcel_acreage)) OVER (), 0), 1)        AS pct_area,
                COUNT(*) FILTER (WHERE mmh_feasibility_flag)                  AS mmh_feasible
            FROM parcels
            WHERE {where} AND zone_code IS NOT NULL
            GROUP BY zone_code, zo_district_name
            ORDER BY acreage DESC
            LIMIT 15
        """).fetchdf()

    finally:
        con.close()

    metrics = agg.iloc[0].to_dict()
    metrics["zone_breakdown"] = zone_df

    # Street miles per acre (live spatial computation)
    try:
        metrics["street_miles_per_acre"] = _compute_street_miles_per_acre(wkt_2868)
    except Exception as e:
        print(f"Street miles computation skipped: {e}")
        metrics["street_miles_per_acre"] = None

    return metrics


def _compute_street_miles_per_acre(wkt_2868: str) -> float | None:
    shp_path = next(STREETS_SHP.glob("*.shp"), None)
    if not shp_path:
        return None
    from shapely.wkt import loads as wkt_loads
    polygon = wkt_loads(wkt_2868)
    acreage = polygon.area / 43_560.0
    if acreage < 0.01:
        return None
    streets = gpd.read_file(shp_path, mask=polygon)
    if streets.empty:
        return None
    clipped     = streets.clip(polygon)
    total_miles = clipped.geometry.length.sum() / 5280.0
    return total_miles / acreage


# ── Parcel detail ─────────────────────────────────────────────────────────────

def get_parcel_detail(parcel_id: str) -> dict | None:
    con = _con()
    try:
        result = con.execute(f"""
            SELECT
                parcel_id, situs_full_address, situs_city, situs_zip,
                zone_code, zone_code_raw, zo_district_name, zo_district_type,
                property_use_code, owner_name,
                parcel_acreage, year_built, stories,
                total_floor_area_sqft, num_units,
                full_cash_value, land_fcv, improvement_fcv,
                lpv_amount, land_value_per_acre, lpv_per_acre,
                improvement_to_land_ratio,
                zoning_capacity_du, upzoning_gap_du,
                lodes_jobs_apportioned, jobs_per_acre,
                acs_transit_mode_share,
                mmh_feasibility_flag, is_underutilized,
                is_vacant, sec711_candidate_flag,
                urban_village, tod_district_name_full,
                hp_flag, dvao_flag, is_exempt, is_county_parcel
            FROM parcels
            WHERE parcel_id = '{parcel_id}'
            LIMIT 1
        """).fetchdf()
    finally:
        con.close()
    if result.empty:
        return None
    return result.iloc[0].to_dict()


# ── Choropleth viewport query ─────────────────────────────────────────────────

def get_parcels_in_viewport(
    min_lon: float, min_lat: float,
    max_lon: float, max_lat: float,
    layer: str = "mmh",
    zone_codes: list | None = None,
) -> dict:
    # Project bbox to EPSG:2868
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[shape({"type": "Polygon", "coordinates": [[
            [min_lon, min_lat], [max_lon, min_lat],
            [max_lon, max_lat], [min_lon, max_lat],
            [min_lon, min_lat],
        ]]})],
        crs="EPSG:4326",
    ).to_crs(PROJECT_CRS)
    bbox_wkt = bbox_gdf.geometry.iloc[0].wkt

    if zone_codes:
        quoted     = ", ".join(f"'{z}'" for z in zone_codes)
        layer_cond = f"zone_code IN ({quoted})"
    else:
        layer_cond = LAYER_CONDITIONS.get(layer, LAYER_CONDITIONS["mmh"])

    con = _con()
    try:
        result = con.execute(f"""
            SELECT
                parcel_id,
                ST_AsWKB(geom)         AS geom_wkb,
                zone_code,
                lpv_per_acre,
                upzoning_gap_du,
                mmh_feasibility_flag,
                is_underutilized,
                sec711_candidate_flag,
                in_tod_district
            FROM parcels
            WHERE ST_Within(geom, ST_GeomFromText('{bbox_wkt}'))
              AND {layer_cond}
              AND NOT COALESCE(is_exempt, FALSE)
              AND NOT COALESCE(is_county_parcel, FALSE)
            LIMIT {MAX_PARCELS_IN_VIEW}
        """).fetchdf()
    finally:
        con.close()

    if result.empty:
        return {"type": "FeatureCollection", "features": []}

    # Reproject WKB from EPSG:2868 → WGS84 in Python
    geoms = [shapely_wkb.loads(bytes(b)) for b in result["geom_wkb"]]
    gdf   = gpd.GeoDataFrame(
        result.drop(columns=["geom_wkb"]),
        geometry=geoms, crs=PROJECT_CRS,
    ).to_crs("EPSG:4326")

    def parcel_color(row) -> str:
        if zone_codes:
            if row.get("mmh_feasibility_flag"):  return COLOR_MMH
            if row.get("is_underutilized"):       return COLOR_UNDERUTILIZED
            if row.get("sec711_candidate_flag"):  return COLOR_SEC711
            if row.get("in_tod_district"):        return COLOR_TOD
            return COLOR_NEUTRAL
        color_map = {
            "mmh":   COLOR_MMH,
            "under": COLOR_UNDERUTILIZED,
            "s711":  COLOR_SEC711,
            "tod":   COLOR_TOD,
            "none":  COLOR_NEUTRAL,
        }
        return color_map.get(layer, COLOR_MMH)

    features = []
    for _, row in gdf.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "parcel_id":    row["parcel_id"],
                "zone_code":    row["zone_code"],
                "lpv_per_acre": row.get("lpv_per_acre"),
                "upzoning_gap": row.get("upzoning_gap_du"),
                "color":        parcel_color(row),
            },
            "geometry": mapping(row["geometry"]),
        })
    return {"type": "FeatureCollection", "features": features}


# ── Context layer loaders ─────────────────────────────────────────────────────

def _load_shp_as_geojson(
    shp_dir: Path,
    filter_func=None,
    simplify_tolerance: float = 0,
) -> dict:
    shp_path = next(shp_dir.glob("*.shp"), None) if shp_dir.is_dir() else None
    if not shp_path:
        return {"type": "FeatureCollection", "features": []}
    gdf = gpd.read_file(shp_path)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    if filter_func:
        gdf = filter_func(gdf)
    if simplify_tolerance:
        gdf["geometry"] = gdf.geometry.simplify(simplify_tolerance)
    features = []
    for _, row in gdf.iterrows():
        props = {k: str(v) for k, v in row.drop("geometry").items()
                 if v is not None and str(v) not in ("nan", "")}
        features.append({
            "type":       "Feature",
            "properties": props,
            "geometry":   mapping(row.geometry),
        })
    return {"type": "FeatureCollection", "features": features}


@lru_cache(maxsize=1)
def load_city_limits() -> dict:
    return _load_shp_as_geojson(CITY_LIMITS_SHP, simplify_tolerance=0.0001)


@lru_cache(maxsize=1)
def load_dpi_boundary() -> dict:
    return _load_shp_as_geojson(DPI_SHP, simplify_tolerance=0.0001)


@lru_cache(maxsize=1)
def load_light_rail() -> dict:
    return _load_shp_as_geojson(LIGHT_RAIL_SHP)


@lru_cache(maxsize=1)
def load_arterials() -> dict:
    return _load_shp_as_geojson(
        STREETS_SHP,
        filter_func=lambda gdf: gdf[gdf["STREETCLAS"].isin(ARTERIAL_CLASSES)],
    )


def load_parks() -> dict:
    return _load_shp_as_geojson(PARKS_SHP, simplify_tolerance=0.0001)


def load_zoning_polygons() -> dict:
    shp_path = next(ZONING_DIR.glob("Zoning/*.shp"), None)
    if not shp_path:
        return {"type": "FeatureCollection", "features": []}
    gdf = gpd.read_file(shp_path)
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
    gdf["geometry"] = gdf.geometry.simplify(0.0001)
    features = []
    for _, row in gdf.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "zone":  row.get("ZONING", ""),
                "label": row.get("LABEL1", ""),
            },
            "geometry": mapping(row["geometry"]),
        })
    return {"type": "FeatureCollection", "features": features}


def get_village_geojson_with_metrics() -> dict:
    con = _con()
    try:
        vm = con.execute("""
            SELECT
                urban_village,
                SUM(lpv_amount) / NULLIF(SUM(parcel_acreage), 0) AS lpv_per_acre,
                COUNT(*) FILTER (WHERE mmh_feasibility_flag)       AS mmh_feasible,
                COUNT(*)                                            AS total_parcels
            FROM parcels
            WHERE urban_village IS NOT NULL
              AND NOT COALESCE(is_exempt, FALSE)
            GROUP BY urban_village
        """).fetchdf()
    finally:
        con.close()

    villages = load_village_boundaries()
    merged   = villages.merge(vm, left_on="name", right_on="urban_village", how="left")
    features = []
    for _, row in merged.iterrows():
        features.append({
            "type": "Feature",
            "properties": {
                "name":         row["name"],
                "lpv_per_acre": row.get("lpv_per_acre"),
                "mmh_feasible": row.get("mmh_feasible"),
                "total_parcels":row.get("total_parcels"),
            },
            "geometry": mapping(row["geometry"]),
        })
    return {"type": "FeatureCollection", "features": features}


# ── Startup preload ───────────────────────────────────────────────────────────

def preload() -> None:
    load_village_boundaries()
    load_tod_boundaries()
    load_city_limits()
    load_dpi_boundary()
    load_light_rail()
    load_arterials()
