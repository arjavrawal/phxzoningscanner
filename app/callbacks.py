"""
callbacks.py — Phoenix Upzoning Scanner
All Dash callbacks.
"""

import math

import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, no_update, html, dash_table, dcc
import dash_bootstrap_components as dbc

from config import (
    METRICS, MODE_SHARE_FIELDS,
    TEXT_PRIMARY, TEXT_MUTED, CARD_BG,
    COLOR_MMH, COLOR_UNDERUTILIZED, COLOR_SEC711, COLOR_TOD, COLOR_NEUTRAL,
    CHOROPLETH_MIN_LAT_SPAN, ANALYSIS_LAYERS,
)
from queries import (
    get_geography_geojson, get_geography_center_zoom,
    geojson_feature_to_wkt_2868,
    get_scorecard, get_parcels_in_viewport,
    get_village_geojson_with_metrics,
    get_all_zone_codes, get_zone_codes_in_polygon,
    get_parcel_detail, _con,
    load_city_limits, load_dpi_boundary, load_light_rail,
    load_arterials, load_parks, load_zoning_polygons,
)

import geopandas as gpd


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val, fmt) -> str:
    if val is None:
        return "—"
    try:
        if isinstance(val, float) and math.isnan(val):
            return "—"
    except Exception:
        pass
    if callable(fmt):
        try:
            return fmt(val)
        except Exception:
            return str(val)
    try:
        return fmt.format(val)
    except Exception:
        return str(val)


def _metric_card(label: str, value: str, desc: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([
            html.P(label, style={"color": TEXT_MUTED, "fontSize": "0.72rem",
                                  "textTransform": "uppercase",
                                  "letterSpacing": "0.05em", "margin": 0}),
            html.H5(value, style={"color": TEXT_PRIMARY, "fontWeight": 700,
                                   "margin": "2px 0 0"}),
            html.P(desc,  style={"color": TEXT_MUTED, "fontSize": "0.7rem",
                                  "margin": 0}),
        ]),
        style={"background": CARD_BG, "border": "1px solid #2A2A4A",
               "borderRadius": "6px"},
        className="mb-2",
    )


def _metric_cards(data: dict, tab_key: str) -> list:
    cards = []
    for label, col, fmt, desc in METRICS.get(tab_key, []):
        cards.append(_metric_card(label, _fmt(data.get(col), fmt), desc))
    return cards


def _build_scorecard_tabs(data: dict) -> dbc.Tabs:
    total_parcels = data.get("total_parcels") or 0
    total_acreage = data.get("total_acreage") or 0
    mmh_pct = (data.get("mmh_feasible_parcels") or 0) / max(total_parcels, 1) * 100

    # ── Tab 1: Overview ───────────────────────────────────────────────────────
    overview = html.Div([
        html.P(
            f"{_fmt(total_parcels, '{:,.0f}')} parcels · "
            f"{_fmt(total_acreage, '{:,.1f}')} acres",
            style={"color": TEXT_MUTED, "fontSize": "0.8rem",
                   "textAlign": "center", "marginBottom": "12px"},
        ),
        *_metric_cards(data, "overview"),
        dbc.Progress(
            value=mmh_pct,
            label=f"{mmh_pct:.1f}% MMH feasible",
            color="info",
            style={"height": "18px", "fontSize": "0.72rem", "marginTop": "8px"},
        ),
    ])

    # ── Tab 2: Housing ────────────────────────────────────────────────────────
    zone_df  = data.get("zone_breakdown")
    zone_tbl = html.Div()
    if zone_df is not None and not zone_df.empty:
        zone_tbl = html.Div([
            html.P("Zone Breakdown",
                   style={"color": TEXT_MUTED, "fontSize": "0.72rem",
                           "textTransform": "uppercase", "letterSpacing": "0.05em",
                           "marginTop": "12px", "marginBottom": "6px"}),
            dash_table.DataTable(
                data=(zone_df[["zone_code", "acreage", "pct_area", "mmh_feasible"]]
                      .rename(columns={"zone_code": "Zone", "acreage": "Acres",
                                       "pct_area": "% Area", "mmh_feasible": "MMH ✓"})
                      .to_dict("records")),
                columns=[
                    {"name": "Zone",   "id": "Zone"},
                    {"name": "Acres",  "id": "Acres",  "type": "numeric",
                     "format": {"specifier": ",.1f"}},
                    {"name": "% Area", "id": "% Area", "type": "numeric",
                     "format": {"specifier": ".1f"}},
                    {"name": "MMH ✓",  "id": "MMH ✓",  "type": "numeric",
                     "format": {"specifier": ",.0f"}},
                ],
                style_table={"overflowX": "auto"},
                style_cell={"background": CARD_BG, "color": TEXT_PRIMARY,
                             "border": "1px solid #2A2A4A",
                             "fontSize": "11px", "padding": "4px 8px",
                             "textAlign": "left"},
                style_header={"background": "#0F3460", "color": TEXT_PRIMARY,
                               "fontWeight": 700, "fontSize": "11px",
                               "border": "1px solid #2A2A4A"},
                page_size=10,
            ),
        ])

    housing = html.Div([*_metric_cards(data, "housing"), zone_tbl])

    # ── Tab 3: Fiscal ─────────────────────────────────────────────────────────
    fiscal = html.Div(_metric_cards(data, "fiscal"))

    # ── Tab 4: Economic + Mode Share ──────────────────────────────────────────
    mode_data = {label: (data.get(col) or 0)
                 for label, col, _ in MODE_SHARE_FIELDS}

    mode_fig = go.Figure()
    for label, col, color in sorted(MODE_SHARE_FIELDS,
                                    key=lambda x: data.get(x[1]) or 0,
                                    reverse=True):
        val = (data.get(col) or 0) * 100
        mode_fig.add_trace(go.Bar(
            x=[val], y=[label],
            orientation="h",
            marker_color=color,
            text=f"{val:.1f}%",
            textposition="outside",
            cliponaxis=False,
        ))

    max_val = max((data.get(col) or 0) for _, col, _ in MODE_SHARE_FIELDS) * 100
    mode_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin={"t": 10, "b": 10, "l": 10, "r": 55},
        height=220,
        xaxis=dict(range=[0, max(max_val * 1.25, 20)],
                   ticksuffix="%", color=TEXT_MUTED,
                   gridcolor="#2A2A4A", showgrid=True),
        yaxis=dict(color=TEXT_PRIMARY, tickfont=dict(size=11)),
    )

    transit_val = (data.get("transit_mode_share") or 0)
    economic = html.Div([
        *_metric_cards(data, "economic"),
        html.P("COMMUTE MODE SHARE",
               style={"color": TEXT_MUTED, "fontSize": "0.72rem",
                       "textTransform": "uppercase", "letterSpacing": "0.05em",
                       "margin": "12px 0 2px"}),
        html.P("ACS 2023 5-year estimates, tract level",
               style={"color": TEXT_MUTED, "fontSize": "0.68rem",
                       "fontStyle": "italic", "margin": "0 0 6px"}),
        dcc.Graph(figure=mode_fig, config={"displayModeBar": False},
                  style={"height": "220px"}),
        # Transit progress bar for quick reference
        dbc.Card(dbc.CardBody([
            html.P("TRANSIT MODE SHARE",
                   style={"color": TEXT_MUTED, "fontSize": "0.72rem",
                           "textTransform": "uppercase",
                           "letterSpacing": "0.05em", "margin": 0}),
            html.H3(f"{transit_val*100:.1f}%",
                    style={"color": COLOR_MMH, "fontWeight": 700,
                            "margin": "4px 0 2px"}),
            html.P("Workers commuting by transit (ACS 2023)",
                   style={"color": TEXT_MUTED, "fontSize": "0.7rem", "margin": 0}),
            dbc.Progress(
                value=min(transit_val * 100, 15) / 15 * 100,
                color="info",
                style={"height": "8px", "marginTop": "10px",
                       "background": "#2A2A4A"},
            ),
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                             "marginTop": "3px"},
                     children=[
                         html.Span("0%",
                                   style={"color": TEXT_MUTED,
                                          "fontSize": "0.65rem"}),
                         html.Span("Phoenix avg: 1.9%",
                                   style={"color": TEXT_MUTED,
                                          "fontSize": "0.65rem"}),
                         html.Span("15%",
                                   style={"color": TEXT_MUTED,
                                          "fontSize": "0.65rem"}),
                     ]),
        ]),
        style={"background": CARD_BG, "border": "1px solid #2A2A4A",
               "borderRadius": "6px", "marginTop": "8px"}),
    ])

    return dbc.Tabs([
        dbc.Tab(overview,  label="Overview",  tab_id="tab-overview",
                activeTabClassName="fw-bold"),
        dbc.Tab(housing,   label="Housing",   tab_id="tab-housing",
                activeTabClassName="fw-bold"),
        dbc.Tab(fiscal,    label="Fiscal",    tab_id="tab-fiscal",
                activeTabClassName="fw-bold"),
        dbc.Tab(economic,  label="Economic",  tab_id="tab-economic",
                activeTabClassName="fw-bold"),
    ], id="scorecard-tabs", active_tab="tab-overview",
       className="scorecard-tabs mt-1")


def _no_polygon_content() -> html.Div:
    """Citywide summary shown before any polygon is drawn."""
    try:
        con = _con()
        data = con.execute("SELECT * FROM scorecard_summary").fetchdf().iloc[0].to_dict()
        con.close()
        data["zone_breakdown"]      = None
        data["street_miles_per_acre"] = None
        return html.Div([
            html.P("CITYWIDE SUMMARY",
                   style={"color": "#7B8CDE", "fontSize": "0.65rem",
                           "fontWeight": 700, "letterSpacing": "0.12em",
                           "textTransform": "uppercase", "marginBottom": "8px"}),
            html.P("Draw a polygon or select a geography to analyze a specific area.",
                   style={"color": TEXT_MUTED, "fontSize": "0.78rem",
                           "marginBottom": "12px"}),
            _build_scorecard_tabs(data),
        ])
    except Exception:
        return html.Div(
            "Draw a polygon or select a geography to see the scorecard.",
            style={"color": TEXT_MUTED, "fontSize": "0.85rem",
                   "textAlign": "center", "marginTop": "24px"},
        )


# ── Overlay parsing for parcel modal ─────────────────────────────────────────

OVERLAY_TOKENS = {
    "SP":       "Special Permit",
    "CUP":      "Conditional Use Permit",
    "SUP":      "Special Use Permit",
    "HP":       "Historic Preservation",
    "HP-L":     "Historic Preservation — Landmark",
    "TOD-1":    "Transit-Oriented Development 1",
    "TOD-2":    "Transit-Oriented Development 2",
    "HRI":      "High-Rise Incentive",
    "HGT/WVR":  "Height Waiver",
    "AIO":      "Airport Influence Overlay",
    "DVAO":     "Deer Valley Airport Overlay",
    "MH":       "Middle Housing Overlay",
    "R-I":      "Residential Infill Overlay",
    "H-R":      "High-Rise Overlay",
    "FHEM":     "Flood Hazard / Environmental Modification",
}


def _build_overlay_section(detail: dict) -> html.Div:
    import re
    raw     = detail.get("zone_code_raw") or ""
    pending = raw.endswith("*")
    clean   = raw.rstrip("* ").strip()

    detected = [
        f"{token} ({label})"
        for token, label in OVERLAY_TOKENS.items()
        if re.search(re.escape(token), clean.upper())
    ]

    return html.Div([
        html.P("LABEL1 (full zoning designation):",
               style={"color": TEXT_MUTED, "fontSize": "0.7rem",
                       "margin": "0 0 2px"}),
        html.Code(raw or "—",
                  style={"background": "#0A0A1A", "color": "#00E5FF",
                          "padding": "3px 7px", "borderRadius": "3px",
                          "fontSize": "0.8rem", "display": "block",
                          "marginBottom": "6px"}),
        html.Div([dbc.Badge("PENDING CASE", color="warning",
                            className="me-1")]) if pending else html.Div(),
        html.Div([
            html.P("Detected overlays / permits:",
                   style={"color": TEXT_MUTED, "fontSize": "0.7rem",
                           "margin": "6px 0 3px"}),
            html.Div([dbc.Badge(o, color="secondary", className="me-1 mb-1")
                      for o in detected]),
        ]) if detected else html.P(
            "No overlays detected in LABEL1.",
            style={"color": TEXT_MUTED, "fontSize": "0.7rem",
                   "margin": "4px 0 0"},
        ),
        html.P(
            "WARNING: Base zoning only. CUPs, SPs, development agreements, and plat "
            "conditions are not fully captured. Verify with the City of Phoenix "
            "website.",
            style={"color": "#FF9800", "fontSize": "0.68rem",
                   "margin": "8px 0 0", "lineHeight": "1.4"},
        ),
    ], style={"background": "#0A0A1A", "border": "1px solid #2A2A4A",
               "borderRadius": "4px", "padding": "8px 10px",
               "marginBottom": "8px"})


# ── Register callbacks ────────────────────────────────────────────────────────

def register_callbacks(app):

    # ── Geography dropdown → polygon store ───────────────────────────────────
    @app.callback(
        Output("active-polygon-store", "data", allow_duplicate=True),
        Input("geography-dropdown", "value"),
        prevent_initial_call=True,
    )
    def geography_to_polygon(geo_value):
        if not geo_value:
            return no_update
        return get_geography_geojson(geo_value)

    # ── EditControl → polygon store ───────────────────────────────────────────
    @app.callback(
        Output("active-polygon-store", "data", allow_duplicate=True),
        Input("edit-control", "geojson"),
        prevent_initial_call=True,
    )
    def draw_to_polygon(geojson):
        if not geojson or not geojson.get("features"):
            return None
        return geojson["features"][-1]

    # ── Clear button ──────────────────────────────────────────────────────────
    @app.callback(
        Output("active-polygon-store", "data", allow_duplicate=True),
        Output("geography-dropdown", "value"),
        Input("clear-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_polygon(n):
        return None, ""

    # ── Polygon → highlight layer ─────────────────────────────────────────────
    @app.callback(
        Output("active-polygon-layer", "data"),
        Input("active-polygon-store", "data"),
    )
    def update_polygon_highlight(feature):
        if not feature:
            return None
        return {"type": "FeatureCollection", "features": [feature]}

    # ── Geography → map center + zoom ─────────────────────────────────────────
    @app.callback(
        Output("main-map", "center"),
        Output("main-map", "zoom"),
        Input("geography-dropdown", "value"),
        prevent_initial_call=True,
    )
    def center_map_on_geography(geo_value):
        if not geo_value:
            return no_update, no_update
        center, zoom = get_geography_center_zoom(geo_value)
        if center is None:
            return no_update, no_update
        return center, zoom

    # ── Layer panel toggle ────────────────────────────────────────────────────
    @app.callback(
        Output("layer-panel-collapse", "is_open"),
        Input("layer-panel-toggle", "n_clicks"),
        State("layer-panel-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_layer_panel(n, is_open):
        return not is_open

    # ── Analysis radio → store + choropleth style ─────────────────────────────
    @app.callback(
        Output("active-layer-store", "data"),
        Output("choropleth-layer", "style"),
        Input("analysis-layer-radio", "value"),
    )
    def update_analysis_layer(layer):
        color_map = {
            "mmh":   COLOR_MMH,
            "under": COLOR_UNDERUTILIZED,
            "s711":  COLOR_SEC711,
            "tod":   COLOR_TOD,
            "none":  COLOR_NEUTRAL,
        }
        color = color_map.get(layer or "mmh", COLOR_MMH)
        return layer, dict(weight=0.8, fillOpacity=0.65,
                           color=color, fillColor=color)

    # ── Context layers checklist → map layers ─────────────────────────────────
    @app.callback(
        Output("ctx-villages",   "data"),
        Output("ctx-zoning",     "data"),
        Output("ctx-citylimits", "data"),
        Output("ctx-dpi",        "data"),
        Output("ctx-lightrail",  "data"),
        Output("ctx-arterials",  "data"),
        Output("ctx-parks",      "data"),
        Input("context-layers-checklist", "value"),
    )
    def update_context_layers(active):
        active = active or []
        empty  = {"type": "FeatureCollection", "features": []}
        def get(key, loader):
            try:
                return loader() if key in active else empty
            except Exception:
                return empty

        return (
            get("villages",   get_village_geojson_with_metrics),
            get("zoning",     load_zoning_polygons),
            get("citylimits", load_city_limits),
            get("dpi",        load_dpi_boundary),
            get("lightrail",  load_light_rail),
            get("arterials",  load_arterials),
            get("parks",      load_parks),
        )

    # ── Choropleth data (bounds + layer + zone filter) ────────────────────────
    @app.callback(
        Output("choropleth-layer", "data"),
        Input("main-map", "bounds"),
        Input("active-layer-store", "data"),
        Input("zone-filter-dropdown", "value"),
        prevent_initial_call=True,
    )
    def update_choropleth_data(bounds, active_layer, zone_codes):
        if not bounds or active_layer == "none":
            return {"type": "FeatureCollection", "features": []}
        south, west = bounds[0]
        north, east = bounds[1]
        if (north - south) > CHOROPLETH_MIN_LAT_SPAN:
            return {"type": "FeatureCollection", "features": []}
        return get_parcels_in_viewport(
            min_lon=west, min_lat=south,
            max_lon=east, max_lat=north,
            layer=active_layer or "mmh",
            zone_codes=zone_codes or None,
        )

    # ── Zone filter: all zones on load, polygon-specific after draw ───────────
    @app.callback(
        Output("zone-filter-dropdown", "options"),
        Output("zone-filter-dropdown", "value"),
        Input("main-map", "id"),
        Input("active-polygon-store", "data"),
        prevent_initial_call=False,
    )
    def update_zone_filter(_, feature):
        if not feature:
            return get_all_zone_codes(), None
        try:
            wkt = geojson_feature_to_wkt_2868(feature)
            return get_zone_codes_in_polygon(wkt), None
        except Exception:
            return get_all_zone_codes(), None

    # ── Zone filter → map zoom ────────────────────────────────────────────────
    @app.callback(
        Output("main-map", "center", allow_duplicate=True),
        Output("main-map", "zoom",   allow_duplicate=True),
        Input("zone-filter-dropdown", "value"),
        prevent_initial_call=True,
    )
    def zoom_to_zone(zone_codes):
        if not zone_codes:
            return no_update, no_update
        quoted = ", ".join(f"'{z}'" for z in zone_codes)
        con = _con()
        try:
            result = con.execute(f"""
                SELECT ST_AsWKB(ST_Centroid(geom)) AS centroid_wkb
                FROM parcels
                WHERE zone_code IN ({quoted})
                  AND NOT COALESCE(is_exempt, FALSE)
                LIMIT 500
            """).fetchdf()
        finally:
            con.close()
        if result.empty:
            return no_update, no_update
        from shapely import wkb as shapely_wkb
        geoms = [shapely_wkb.loads(bytes(b)) for b in result["centroid_wkb"]]
        gdf   = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:2868").to_crs("EPSG:4326")
        b     = gdf.total_bounds   # [minx, miny, maxx, maxy]
        center = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2]
        span   = max(b[3] - b[1], b[2] - b[0])
        if span > 0.2:    zoom = 11
        elif span > 0.1:  zoom = 12
        elif span > 0.05: zoom = 13
        else:             zoom = 14
        return center, zoom

    # ── Polygon store → scorecard ─────────────────────────────────────────────
    @app.callback(
        Output("scorecard-area", "children"),
        Input("active-polygon-store", "data"),
    )
    def update_scorecard(feature):
        if not feature:
            return _no_polygon_content()
        try:
            wkt  = geojson_feature_to_wkt_2868(feature)
            data = get_scorecard(wkt)
        except Exception as e:
            return html.Div(f"Error computing scorecard: {e}",
                            style={"color": "#FF5252", "fontSize": "0.8rem"})
        if not data.get("total_parcels"):
            return html.Div("No non-exempt parcels found in this area.",
                            style={"color": TEXT_MUTED, "fontSize": "0.85rem",
                                   "textAlign": "center", "marginTop": "24px"})
        return _build_scorecard_tabs(data)

    # ── Parcel click → detail modal ───────────────────────────────────────────
    @app.callback(
        Output("parcel-modal",       "is_open"),
        Output("parcel-modal-title", "children"),
        Output("parcel-modal-body",  "children"),
        Input("choropleth-layer",    "clickData"),
        Input("parcel-modal-close",  "n_clicks"),
        State("parcel-modal",        "is_open"),
        prevent_initial_call=True,
    )
    def handle_parcel_click(click_data, close_n, is_open):
        triggered = ctx.triggered_id
        if triggered == "parcel-modal-close":
            return False, no_update, no_update
        if not click_data:
            return no_update, no_update, no_update

        parcel_id = (click_data.get("properties") or {}).get("parcel_id")
        if not parcel_id:
            return no_update, no_update, no_update

        detail = get_parcel_detail(parcel_id)
        if not detail:
            return True, parcel_id, html.P("No detail found.")

        # ── Helpers ───────────────────────────────────────────────────────────
        def row(label, value, fmt=None):
            display = _fmt(value, fmt) if fmt else (str(value) if value is not None else "—")
            return html.Tr([
                html.Td(label,   style={"color": TEXT_MUTED, "fontSize": "0.8rem",
                                         "padding": "4px 12px 4px 0",
                                         "whiteSpace": "nowrap"}),
                html.Td(display, style={"color": TEXT_PRIMARY, "fontSize": "0.8rem",
                                         "fontWeight": 600}),
            ])

        def section(title):
            return html.Tr(html.Td(
                title, colSpan=2,
                style={"color": "#7B8CDE", "fontSize": "0.68rem",
                        "fontWeight": 700, "textTransform": "uppercase",
                        "letterSpacing": "0.1em",
                        "paddingTop": "14px", "paddingBottom": "4px"},
            ))

        # ── Flags ─────────────────────────────────────────────────────────────
        flags = []
        if detail.get("mmh_feasibility_flag"):
            flags.append(dbc.Badge("MMH Feasible",  color="info",      className="me-1"))
        if detail.get("is_underutilized"):
            flags.append(dbc.Badge("Underutilized", color="warning",   className="me-1"))
        if detail.get("sec711_candidate_flag"):
            flags.append(dbc.Badge("§711 Candidate",color="success",   className="me-1"))
        if detail.get("is_vacant"):
            flags.append(dbc.Badge("Vacant",         color="secondary", className="me-1"))
        if detail.get("hp_flag"):
            flags.append(dbc.Badge("Historic HP",    color="danger",    className="me-1"))
        if detail.get("in_tod_district"):
            flags.append(dbc.Badge("TOD District",   color="primary",   className="me-1"))

        # ── Zone display ──────────────────────────────────────────────────────
        zc   = detail.get("zone_code") or ""
        zn   = detail.get("zo_district_name") or ""
        if zn and "placeholder" in zn.lower():
            zn = "Walkable Urban Code"
        zone_display = f"{zc} — {zn}" if zn else zc

        address  = detail.get("situs_full_address") or "—"
        title    = f"{address} · {parcel_id}"

        body = html.Div([
            html.Div(flags, className="mb-3") if flags else html.Div(),

            dbc.Alert(
                "This parcel is tax-exempt (government or nonprofit ownership). "
                "Excluded from upzoning gap and MMH feasibility scoring, "
                "but retains its underlying zoning designation.",
                color="secondary", className="mb-3",
                style={"fontSize": "0.8rem", "padding": "8px 12px"},
            ) if detail.get("is_exempt") else html.Div(),

            dbc.Alert(
                "This parcel is within a Walkable Urban Code (WU) district. "
                "Development standards are governed by the WU transect table "
                "rather than the standard zoning ordinance.",
                color="info", className="mb-3",
                style={"fontSize": "0.8rem", "padding": "8px 12px"},
            ) if detail.get("zone_code") == "WU" else html.Div(),

            _build_overlay_section(detail),

            html.Table([
                section("Parcel Identity"),
                row("APN",           parcel_id),
                row("Address",       detail.get("situs_full_address")),
                row("Base Zone",     zone_display),
                row("Urban Village", detail.get("urban_village")),
                row("TOD District",  detail.get("tod_district_name_full")),
                row("Acreage",       detail.get("parcel_acreage"), "{:.3f} ac"),

                section("Building"),
                row("Year Built",    detail.get("year_built")),
                row("Stories",       detail.get("stories")),
                row("Floor Area",    detail.get("total_floor_area_sqft"),
                    "{:,.0f} sqft"),
                row("Units",         detail.get("num_units"), "{:.0f}"),

                section("Ownership & Value"),
                row("Owner",         detail.get("owner_name")),
                row("Full Cash Value",        detail.get("full_cash_value"),
                    "${:,.0f}"),
                row("Land FCV",               detail.get("land_fcv"),
                    "${:,.0f}"),
                row("Improvement FCV",        detail.get("improvement_fcv"),
                    "${:,.0f}"),
                row("LPV / Acre",             detail.get("lpv_per_acre"),
                    "${:,.0f}"),
                row("Impr / Land Ratio",      detail.get("improvement_to_land_ratio"),
                    "{:.2f}"),

                section("Development Capacity"),
                row("Zoning Capacity", detail.get("zoning_capacity_du"),
                    "{:,.0f} DUs"),
                row("Upzoning Gap",    detail.get("upzoning_gap_du"),
                    "{:,.0f} DUs"),

                section("Activity"),
                row("Jobs (apportioned)", detail.get("lodes_jobs_apportioned"),
                    "{:,.1f}"),
                row("Jobs / Acre",        detail.get("jobs_per_acre"), "{:.2f}"),
                row("Transit Mode Share", detail.get("acs_transit_mode_share"),
                    lambda v: f"{float(v)*100:.1f}%"),
            ], style={"width": "100%", "borderCollapse": "collapse"}),
        ])

        return True, title, body
