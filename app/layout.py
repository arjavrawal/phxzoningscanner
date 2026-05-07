import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html

from config import (
    BASEMAP_URL, BASEMAP_ATTRIBUTION,
    MAP_CENTER, MAP_ZOOM,
    COLOR_POLYGON, COLOR_MMH,
    ANALYSIS_LAYERS, CONTEXT_LAYERS,
    SIDEBAR_BG, CARD_BG, TEXT_PRIMARY, TEXT_MUTED,
)
from queries import get_geography_options


def make_layout() -> html.Div:
    geo_options = get_geography_options()
    
    map_children = [
        dl.TileLayer(
            url=BASEMAP_URL,
            attribution=BASEMAP_ATTRIBUTION,
            maxZoom=20,
        ),

        dl.GeoJSON(id="ctx-villages",   data=None,
                   options={"style": {"color": "#7B8CDE", "weight": 1.5,
                                      "fillColor": "#7B8CDE", "fillOpacity": 0.03}}),
        dl.GeoJSON(id="ctx-zoning",     data=None,
                   options={"style": {"color": "#FF6B6B", "weight": 0.8,
                                      "fillOpacity": 0.0}}),
        dl.GeoJSON(id="ctx-citylimits", data=None,
                   options={"style": {"color": "#FFFFFF", "weight": 2,
                                      "fillOpacity": 0.0, "dashArray": "8 4"}}),
        dl.GeoJSON(id="ctx-dpi",        data=None,
                   options={"style": {"color": "#69F0AE", "weight": 2,
                                      "fillOpacity": 0.0, "dashArray": "4 4"}}),
        dl.GeoJSON(id="ctx-lightrail",  data=None,
                   options={"style": {"color": "#FFD700", "weight": 3,
                                      "fillOpacity": 0.0}}),
        dl.GeoJSON(id="ctx-arterials",  data=None,
                   options={"style": {"color": "#FF9800", "weight": 1.5,
                                      "fillOpacity": 0.0}}),
        dl.GeoJSON(id="ctx-parks",      data=None,
                   options={"style": {"color": "#4CAF50", "weight": 1,
                                      "fillColor": "#4CAF50", "fillOpacity": 0.2}}),

        dl.GeoJSON(
            id="choropleth-layer",
            data=None,
            style=dict(weight=0.8, fillOpacity=0.65,
                       color=COLOR_MMH, fillColor=COLOR_MMH),
            clickData=True,
            zoomToBoundsOnClick=False,
        ),

        dl.GeoJSON(
            id="active-polygon-layer",
            data=None,
            options={"style": {
                "color":       COLOR_POLYGON,
                "weight":      2.5,
                "fillColor":   COLOR_POLYGON,
                "fillOpacity": 0.08,
                "dashArray":   "6 4",
            }},
        ),

        dl.FeatureGroup(children=[
            dl.EditControl(
                id="edit-control",
                position="topleft",
                draw={
                    "polygon":      {"allowIntersection": False,
                                     "shapeOptions": {"color": COLOR_POLYGON,
                                                      "weight": 2}},
                    "rectangle":    {"shapeOptions": {"color": COLOR_POLYGON,
                                                      "weight": 2}},
                    "circle":       False,
                    "circlemarker": False,
                    "marker":       False,
                    "polyline":     False,
                },
                edit={"edit": True, "remove": True},
            ),
        ]),
    ]

    map_component = dl.Map(
        id="main-map",
        center=MAP_CENTER,
        zoom=MAP_ZOOM,
        style={"height": "100vh", "width": "100%"},
        children=map_children,
    )

    layer_panel = html.Div(
        style={
            "position": "absolute", "top": "10px", "right": "10px",
            "zIndex": 1000, "width": "220px",
        },
        children=[
            dbc.Button(
                "⊞  Layers",
                id="layer-panel-toggle",
                size="sm",
                style={
                    "background":    "rgba(22,33,62,0.95)",
                    "border":        "1px solid #2A2A4A",
                    "color":         TEXT_PRIMARY,
                    "width":         "100%",
                    "textAlign":     "left",
                    "marginBottom":  "2px",
                    "fontSize":      "0.8rem",
                },
                n_clicks=0,
            ),
            dbc.Collapse(
                id="layer-panel-collapse",
                is_open=True,
                children=html.Div(
                    style={
                        "background":    "rgba(22,33,62,0.95)",
                        "border":        "1px solid #2A2A4A",
                        "borderRadius":  "4px",
                        "padding":       "10px 12px",
                    },
                    children=[
                        html.P("ANALYSIS LAYER",
                               style={"color": "#7B8CDE", "fontSize": "0.62rem",
                                      "fontWeight": 700, "letterSpacing": "0.1em",
                                      "margin": "0 0 6px"}),
                        dcc.RadioItems(
                            id="analysis-layer-radio",
                            options=[
                                {
                                    "label": html.Span([
                                        html.Span("● ", style={"color": l["color"],
                                                                "fontSize": "1.1em"}),
                                        l["label"],
                                    ], style={"fontSize": "0.8rem",
                                              "color": TEXT_PRIMARY}),
                                    "value": l["value"],
                                }
                                for l in ANALYSIS_LAYERS
                            ],
                            value="mmh",
                            inputStyle={"marginRight": "6px"},
                            labelStyle={"display": "flex", "alignItems": "center",
                                        "marginBottom": "4px"},
                        ),
                        html.Hr(style={"borderColor": "#2A2A4A", "margin": "8px 0"}),
                        html.P("CONTEXT LAYERS",
                               style={"color": "#7B8CDE", "fontSize": "0.62rem",
                                      "fontWeight": 700, "letterSpacing": "0.1em",
                                      "margin": "0 0 6px"}),
                        dcc.Checklist(
                            id="context-layers-checklist",
                            options=[
                                {
                                    "label": html.Span([
                                        html.Span("— ", style={"color": l["color"],
                                                                "fontWeight": 700}),
                                        l["label"],
                                    ], style={"fontSize": "0.8rem",
                                              "color": TEXT_PRIMARY}),
                                    "value": l["value"],
                                }
                                for l in CONTEXT_LAYERS
                            ],
                            value=["villages"],
                            inputStyle={"marginRight": "6px"},
                            labelStyle={"display": "flex", "alignItems": "center",
                                        "marginBottom": "4px"},
                        ),
                    ],
                ),
            ),
        ],
    )

    sidebar = html.Div(
        id="sidebar",
        style={
            "background": SIDEBAR_BG,
            "height":     "100vh",
            "overflowY":  "auto",
            "padding":    "16px",
        },
        children=[
            html.Div([
                html.H5("Phoenix Upzoning Scanner",
                        style={"color": TEXT_PRIMARY, "margin": 0,
                               "fontWeight": 700}),
                html.P("Parcel-level MMH feasibility analysis",
                       style={"color": TEXT_MUTED, "fontSize": "0.8rem",
                               "margin": 0}),
            ], className="mb-3"),

            html.Hr(style={"borderColor": "#333", "margin": "8px 0 16px"}),

            html.P("ANALYZE AREA", className="section-label"),
            dcc.Dropdown(
                id="geography-dropdown",
                options=geo_options,
                value="",
                placeholder="Select Urban Village or TOD district…",
                clearable=True,
                className="dark-dropdown mb-2",
            ),
            html.P(
                "— or draw a polygon on the map —",
                style={"color": TEXT_MUTED, "fontSize": "0.75rem",
                       "textAlign": "center", "margin": "4px 0 12px"},
            ),
            dbc.Button(
                "✕  Clear polygon",
                id="clear-btn",
                color="secondary",
                outline=True,
                size="sm",
                className="w-100 mb-3",
                style={"fontSize": "0.75rem"},
            ),

            html.Hr(style={"borderColor": "#333", "margin": "8px 0 16px"}),

            html.P("FILTER BY ZONE", className="section-label"),
            dcc.Dropdown(
                id="zone-filter-dropdown",
                options=[],
                value=None,
                placeholder="All zones…",
                clearable=True,
                multi=True,
                className="dark-dropdown mb-3",
            ),

            html.Hr(style={"borderColor": "#333", "margin": "8px 0 16px"}),

            html.Div(id="scorecard-area"),
        ],
    )

    parcel_modal = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="parcel-modal-title")),
        dbc.ModalBody(id="parcel-modal-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="parcel-modal-close",
                       className="ms-auto", n_clicks=0)
        ),
    ], id="parcel-modal", size="lg", is_open=False, scrollable=True)

    stores = html.Div([
        dcc.Store(id="active-polygon-store"),
        dcc.Store(id="active-layer-store",  data="mmh"),
        dcc.Store(id="zone-filter-store",   data=None),
    ])

    return html.Div([
        stores,
        parcel_modal,
        html.Div(
            style={"position": "relative", "height": "100vh"},
            children=[
                dbc.Row(
                    [
                        dbc.Col(map_component, width=8, className="p-0"),
                        dbc.Col(sidebar,       width=4, className="p-0"),
                    ],
                    className="g-0",
                    style={"height": "100vh", "overflow": "hidden"},
                ),
                layer_panel,
            ],
        ),
    ])