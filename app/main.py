import dash
import dash_bootstrap_components as dbc

from layout import make_layout
from callbacks import register_callbacks
from queries import preload

preload()

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        dbc.icons.FONT_AWESOME,
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        "https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css",
    ],
    title="Phoenix Zoning Scanner",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport",
                "content": "width=device-width, initial-scale=1"}],
)

app.layout = make_layout()
register_callbacks(app)
server = app.server

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
