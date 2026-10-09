"""Colours and the Plotly template shared by every chart of the app.

Palette (colour-blind checked, see README):
* observed      : near-black ink - the reference series
* corrected     : blue   (categorical slot 1)
* persistence   : orange (categorical slot 2)
* raw GloFAS    : neutral grey, dashed - de-emphasised, hidden by default
* alerts        : fixed status colours, always shown with an icon + label
"""
import plotly.graph_objects as go
import plotly.io as pio

INK = "#1f2937"
MUTED = "#6b7280"
GRID = "#e8ecf1"
BLUE = "#2a78d6"
BLUE_DARK = "#1c5cab"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RAW = "#9aa3ad"
BAND = "rgba(42,120,214,0.14)"
BAND_IQR = "rgba(42,120,214,0.28)"

STATUS = {"Normal": "#0ca30c", "Vigilance": "#fab219", "Alerte": "#ec835a", "Alerte maximale": "#d03b3b"}
ICONS = {"Normal": "🟢", "Vigilance": "🟡", "Alerte": "🟠", "Alerte maximale": "🔴"}

# diverging red <-> grey <-> blue (good = blue)
DIVERGING = [[0.0, "#b2272f"], [0.25, "#e88a85"], [0.5, "#f0efec"], [0.75, "#86b6ef"], [1.0, "#184f95"]]
SEQ_BLUE = [[0.0, "#eef4fc"], [0.35, "#9ec5f4"], [0.7, "#3987e5"], [1.0, "#104281"]]
SEQ_ORANGE = [[0.0, "#fdf1ea"], [0.4, "#f6b38f"], [0.75, "#eb6834"], [1.0, "#a83c12"]]

pio.templates["rusizi"] = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color=INK),
        paper_bgcolor="white", plot_bgcolor="white",
        colorway=[BLUE, ORANGE, AQUA],
        xaxis=dict(showgrid=False, linecolor="#c9d1da", ticks="outside", tickcolor="#c9d1da", zeroline=False),
        yaxis=dict(gridcolor=GRID, linecolor="rgba(0,0,0,0)", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#c9d1da"),
        margin=dict(l=10, r=10, t=60, b=10),
        title=dict(font=dict(size=15, color=INK), x=0, xanchor="left"),
    )
)
pio.templates.default = "rusizi"

# Plotly toolbar: high-resolution PNG download, no logo, fewer buttons
PLOTLY_CONFIG = {
    "displaylogo": False,
    "toImageButtonOptions": {"format": "png", "scale": 3},
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}

APP_CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1350px;}
h1 {color: #12395f; font-weight: 700; letter-spacing: -0.3px;}
h2, h3 {color: #12395f;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #0f3d63 0%, #165a8a 100%);}
[data-testid="stSidebarNav"] *, [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *, [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {color: #eaf2fa !important;}
[data-testid="stSidebar"] [data-baseweb="select"] > div {background: #ffffff; border-radius: 8px;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color: #12395f !important; -webkit-text-fill-color: #12395f !important;
    opacity: 1 !important;}
[data-testid="stSidebarNav"] a:hover {background: rgba(255,255,255,0.08);}
div[data-testid="stMetric"] {background: #f3f6fa; border: 1px solid #e3e9f0; border-radius: 10px; padding: 10px 14px;}
div[data-testid="stMetricLabel"] p {color: #4b5563;}
div[data-testid="stMetricValue"] {font-size: 1.55rem;}
div[data-testid="stMetricValue"] > div {white-space: normal; overflow: visible; text-overflow: clip;}
.hero {background: linear-gradient(90deg, #0f3d63, #2a78d6); color: white; padding: 18px 22px;
       border-radius: 12px; margin-bottom: 14px;}
.hero h2 {color: white; margin: 0 0 4px 0; font-size: 1.45rem;}
.hero p {color: #e6effa; margin: 0;}
.pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.85rem; font-weight:600;}
</style>
"""
