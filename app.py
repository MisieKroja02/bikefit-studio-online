from __future__ import annotations

import html
import ipaddress
import json
import math
import socket
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from bikefit.internet_import import fetch_geometry
from bikefit.kinematics import analyze_cycle, bike_points, calculate_pose
from bikefit.models import BikeGeometry, FitSettings, Rider
from bikefit.optimizer import optimize_fit
from bikefit.recommendations import measurement_guide, recommend_and_evaluate
from bikefit.tire_pressure import (
    CASING_FACTORS,
    GOAL_OFFSETS_BAR,
    SETUP_FACTORS,
    SURFACE_FACTORS,
    calculate_tire_pressure,
    suggested_front_load_percent,
)


ROOT = Path(__file__).resolve().parent
BIKES_FILE = ROOT / "data" / "bikes.json"
LOGO_FILE = ROOT / "assets" / "logo_misiek.png"

st.set_page_config(
    page_title="BikeFit Studio Online v1.6 — MisieK",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSS = """
<style>
:root {
  --bg: #07111b;
  --panel: #101d2a;
  --panel2: #172839;
  --line: #30485e;
  --text: #eef7ff;
  --muted: #9db3c7;
  --accent: #67e4b5;
  --accent2: #78baff;
  --warn: #ffd166;
}
.stApp { background: radial-gradient(circle at 50% 8%, #12304a 0%, #08131e 40%, #06101a 100%); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #101d2a 0%, #0b1722 100%); border-right: 1px solid #2d4357; }
[data-testid="stSidebar"] { color: var(--text); }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span:not([data-baseweb="tag"] span) { color: var(--text); }
.block-container { padding-top: 1rem; padding-bottom: 3rem; }
.brand-card {
  display:flex; align-items:center; gap:14px; padding:14px 16px; margin-bottom:12px;
  background:linear-gradient(135deg,#152b3d,#0e1c29); border:1px solid #36536b;
  border-radius:18px; box-shadow:0 12px 30px rgba(0,0,0,.18);
}
.brand-title {font-size:1.5rem; font-weight:800; letter-spacing:.02em; color:#f7fbff; line-height:1.1;}
.brand-sub {font-size:.85rem;color:#9fb5c8;margin-top:3px;}
.hero {
  padding:20px 22px; border-radius:20px; margin-bottom:14px;
  background:linear-gradient(135deg,rgba(23,48,69,.96),rgba(12,27,40,.96));
  border:1px solid #3a5870; box-shadow:0 18px 40px rgba(0,0,0,.22);
}
.hero h1 {margin:0 0 6px 0; font-size:2rem; color:#f4fbff;}
.hero p {margin:0;color:#acc1d3;}
.metric-card {
  padding:14px 16px; border-radius:16px; background:linear-gradient(180deg,#162839,#10202e);
  border:1px solid #344f65; min-height:108px;
}
.metric-label {font-size:.78rem; color:#9fb5c7; text-transform:uppercase; letter-spacing:.06em;}
.metric-value {font-size:1.6rem; font-weight:800; color:#f7fbff; margin-top:3px;}
.metric-note {font-size:.8rem; color:#8fa7bb; margin-top:3px;}
.info-card {padding:15px 17px;border-radius:16px;background:#10202e;border:1px solid #314b61;margin-bottom:10px;}
.small-muted {color:#9fb5c7;font-size:.85rem;}
.measure-grid {display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px;margin:8px 0 14px;}
.measure-card {padding:12px;border-radius:14px;background:#101f2d;border:1px solid #314b61;}
.measure-code {font-weight:900;font-size:1rem;}
.measure-name {color:#b8cad9;font-size:.78rem;min-height:34px;margin-top:4px;}
.measure-value {color:#f8fbff;font-size:1.1rem;font-weight:800;margin-top:5px;}
.footer-note {text-align:center;color:#8399ab;font-size:.78rem;margin-top:28px;}
div[data-baseweb="select"] > div {background:#162838 !important;color:#f5fbff !important;border-color:#3c5b73 !important;}
div[data-baseweb="select"] input {color:#f5fbff !important;-webkit-text-fill-color:#f5fbff !important;}
div[data-baseweb="popover"] {color:#f5fbff !important;}
ul[role="listbox"] {background:#162838 !important;}
li[role="option"] {color:#f5fbff !important;background:#162838 !important;}
li[role="option"]:hover, li[role="option"][aria-selected="true"] {background:#315272 !important;color:#ffffff !important;}

/* Czytelne pola tekstowe i liczbowe w całej aplikacji. */
[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stNumberInput"] div[data-baseweb="input"],
[data-testid="stTextArea"] div[data-baseweb="textarea"] {
  background:#162838 !important;
  border-color:#3c5b73 !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
  background:#162838 !important;
  color:#f7fbff !important;
  -webkit-text-fill-color:#f7fbff !important;
  caret-color:#ffffff !important;
  opacity:1 !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
  color:#91a8bb !important;
  -webkit-text-fill-color:#91a8bb !important;
  opacity:1 !important;
}
[data-testid="stNumberInput"] button {
  background:#253d52 !important;
  color:#ffffff !important;
  border-color:#3c5b73 !important;
}
[data-testid="stNumberInput"] button svg {fill:#ffffff !important;color:#ffffff !important;}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {color:#eaf4fc !important;}

/* Zakładki muszą być widoczne na ciemnym tle. */
[data-testid="stTabs"] button {color:#a9bed0 !important;opacity:1 !important;font-weight:650 !important;}
[data-testid="stTabs"] button:hover {color:#ffffff !important;}
[data-testid="stTabs"] button[aria-selected="true"] {color:#ffffff !important;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background:#67e4b5 !important;}

[data-testid="stMetricValue"] {color:#f6fbff;}
[data-testid="stMetricLabel"] {color:#a9bed0;}

/* Natywne widżety w panelu bocznym — bez białego tekstu na białym tle. */
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-baseweb="textarea"],
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
  background-color:#112435 !important;
  border-color:#3d607a !important;
  color:#f7fbff !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
  background-color:#112435 !important;
  color:#f7fbff !important;
  -webkit-text-fill-color:#f7fbff !important;
  caret-color:#ffffff !important;
  opacity:1 !important;
}
[data-testid="stSidebar"] input::placeholder,
[data-testid="stSidebar"] textarea::placeholder {
  color:#8fa9bd !important;
  -webkit-text-fill-color:#8fa9bd !important;
  opacity:1 !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
  background:#27455e !important;
  color:#ffffff !important;
  border-color:#416681 !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button svg {
  fill:#ffffff !important; color:#ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
  background:#0d1b28 !important;
  border:1px solid #385870 !important;
  border-radius:12px !important;
  overflow:hidden !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  background:#173047 !important;
  color:#ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
  background:#21415d !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg,
[data-testid="stSidebar"] [data-testid="stExpander"] label,
[data-testid="stSidebar"] [data-testid="stExpander"] p {
  color:#f5fbff !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color:#a7bed1 !important;
}
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stDownloadButton > button {
  background:#173047 !important;
  color:#ffffff !important;
  border:1px solid #466985 !important;
}
[data-testid="stSidebar"] .stButton > button:hover,
[data-testid="stSidebar"] .stDownloadButton > button:hover {
  background:#214661 !important;
  color:#ffffff !important;
  border-color:#6d9abc !important;
}
.external-link-btn {
  display:block;
  width:100%;
  box-sizing:border-box;
  padding:0.52rem 0.68rem;
  margin:0.30rem 0;
  border-radius:0.55rem;
  border:1px solid #466985;
  background:#173047;
  color:#ffffff !important;
  font-weight:700;
  font-size:0.88rem;
  line-height:1.15rem;
  text-decoration:none !important;
  text-align:center;
  box-shadow:none;
}
.external-link-btn:visited { color:#ffffff !important; }
.external-link-btn:hover {
  background:#214661;
  color:#ffffff !important;
  border-color:#6d9abc;
  text-decoration:none !important;
}
.external-link-btn:focus {
  outline:2px solid #67e4b5;
  outline-offset:2px;
}
[data-testid="stSidebar"] [data-testid="stAlert"] {
  color:#f7fbff !important;
}
.stButton > button, .stDownloadButton > button {border-radius:12px;font-weight:700;}
@media (max-width: 900px) {.measure-grid{grid-template-columns:1fr 1fr}.hero h1{font-size:1.55rem}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data

def load_bikes() -> list[BikeGeometry]:
    payload = json.loads(BIKES_FILE.read_text(encoding="utf-8"))
    return [BikeGeometry.from_dict(item) for item in payload]


GEOMETRY_FIELDS = [
    ("Stack [mm]", "stack", 0.5),
    ("Reach [mm]", "reach", 0.5),
    ("Kąt rury podsiodłowej [°]", "seat_tube_angle", 0.1),
    ("Kąt główki [°]", "head_tube_angle", 0.1),
    ("Długość główki [mm]", "head_tube_length", 0.5),
    ("Rura podsiodłowa [mm]", "seat_tube_length", 0.5),
    ("Efektywna rura górna [mm]", "top_tube", 0.5),
    ("BB drop [mm]", "bb_drop", 0.5),
    ("Chainstay [mm]", "chainstay", 0.5),
    ("Rozstaw osi [mm]", "wheelbase", 0.5),
    ("Offset widelca [mm]", "fork_offset", 0.5),
    ("Promień koła z oponą [mm]", "wheel_radius", 0.5),
    ("Długość mostka [mm]", "stem_length", 0.5),
    ("Kąt mostka [°]", "stem_angle", 0.5),
    ("Zasięg do chwytu [mm]", "hood_reach", 0.5),
    ("Długość korby [mm]", "crank_length", 0.5),
]


def external_link_button(label: str, url: str) -> None:
    """Renderuje niezawodny ciemny przycisk-link niezależny od motywu Streamlit."""
    safe_label = html.escape(label)
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f'<a class="external-link-btn" href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>',
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "profile_name": "Robert",
        "height": 1780.0,
        "inseam": 830.0,
        "weight": 101.0,
        "flexibility": "Średnia",
        "style": "Zrównoważona",
        "saddle_height": 738.0,
        "saddle_fore_aft": 0.0,
        "handlebar_stack_delta": 0.0,
        "handlebar_reach_delta": 0.0,
        "cadence": 85.0,
        "foot_angle": -8.0,
        "gear_weight": 1.5,
        "tire_setup": "Tubeless",
        "tire_surface": "Typowy asfalt",
        "tire_casing": "Standard",
        "pressure_goal": "Zrównoważone",
        "front_load_percent": 44.0,
        "phase": 270.0,
        "show_measurements": True,
        "simulation_scale": 82.0,
        "animate_crank": False,
        "show_angles": True,
        "animation_phase": 270.0,
        "animation_last_ts": None,
        "fit_notes": [],
        "custom_bikes": [],
        "sidebar_import_url": "",
        "sidebar_import_status": "",
        "sidebar_import_notes": [],
        "pending_settings": None,
        "pending_fit_notes": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def current_settings() -> FitSettings:
    return FitSettings(
        saddle_height=float(st.session_state.saddle_height),
        saddle_fore_aft=float(st.session_state.saddle_fore_aft),
        handlebar_stack_delta=float(st.session_state.handlebar_stack_delta),
        handlebar_reach_delta=float(st.session_state.handlebar_reach_delta),
        cadence=float(st.session_state.cadence),
        foot_angle=float(st.session_state.foot_angle),
        style=str(st.session_state.style),
        gear_weight=float(st.session_state.gear_weight),
        tire_setup=str(st.session_state.tire_setup),
        tire_surface=str(st.session_state.tire_surface),
        tire_casing=str(st.session_state.tire_casing),
        pressure_goal=str(st.session_state.pressure_goal),
        front_load_percent=float(st.session_state.front_load_percent),
    )


def current_rider() -> Rider:
    return Rider.from_height_inseam(
        str(st.session_state.profile_name),
        float(st.session_state.height),
        float(st.session_state.inseam),
        str(st.session_state.flexibility),
        float(st.session_state.weight),
    )


def bike_catalog() -> list[BikeGeometry]:
    bikes = list(load_bikes())
    for payload in st.session_state.custom_bikes:
        custom = BikeGeometry.from_dict(payload)
        if not any(b.name == custom.name for b in bikes):
            bikes.append(custom)
    return bikes


def reset_geometry_state(bike: BikeGeometry) -> None:
    st.session_state.geo_name = bike.name
    st.session_state.geo_type = bike.bike_type
    for field in (
        "stack", "reach", "seat_tube_angle", "head_tube_angle", "head_tube_length",
        "seat_tube_length", "top_tube", "bb_drop", "chainstay", "wheelbase",
        "fork_offset", "wheel_radius", "stem_length", "stem_angle", "hood_reach",
        "crank_length", "bike_weight", "tire_width_front", "tire_width_rear",
        "tire_max_pressure",
    ):
        st.session_state[f"geo_{field}"] = float(getattr(bike, field))


def geometry_from_state(fallback: BikeGeometry) -> BikeGeometry:
    payload = fallback.to_dict()
    payload["name"] = str(st.session_state.get("geo_name", fallback.name))
    payload["bike_type"] = str(st.session_state.get("geo_type", fallback.bike_type))
    for field in payload:
        key = f"geo_{field}"
        if key in st.session_state and field not in ("name", "bike_type"):
            payload[field] = float(st.session_state[key])
    return BikeGeometry.from_dict(payload)


SETTINGS_KEYS = (
    "saddle_height", "saddle_fore_aft", "handlebar_stack_delta",
    "handlebar_reach_delta", "cadence", "foot_angle", "style",
    "gear_weight", "tire_setup", "tire_surface", "tire_casing",
    "pressure_goal", "front_load_percent",
)


def queue_settings(settings: FitSettings, notes: list[str] | None = None) -> None:
    """Zapisuje zmiany do zastosowania na początku następnego przebiegu Streamlit.

    Streamlit blokuje bezpośrednią zmianę session_state dla klucza widżetu
    po utworzeniu tego widżetu w bieżącym przebiegu. Kolejka eliminuje ten
    błąd przy przyciskach doboru i optymalizacji.
    """
    st.session_state.pending_settings = {key: getattr(settings, key) for key in SETTINGS_KEYS}
    if notes is not None:
        st.session_state.pending_fit_notes = list(notes)


def apply_pending_state() -> None:
    pending = st.session_state.get("pending_settings")
    if pending:
        for key, value in pending.items():
            st.session_state[key] = value
        st.session_state.pending_settings = None
    notes = st.session_state.get("pending_fit_notes")
    if notes is not None:
        st.session_state.fit_notes = list(notes)
        st.session_state.pending_fit_notes = None

def display_phase_deg() -> float:
    base_phase = float(st.session_state.get("phase", 270.0))
    if not bool(st.session_state.get("animate_crank", False)):
        st.session_state.animation_last_ts = None
        st.session_state.animation_phase = base_phase
        return base_phase

    now = time.time()
    current = float(st.session_state.get("animation_phase", base_phase))
    last = st.session_state.get("animation_last_ts")
    if last is None:
        current = base_phase
    else:
        dt = max(0.0, min(0.5, now - float(last)))
        current = (current + dt * float(st.session_state.get("cadence", 85.0)) * 6.0) % 360.0
    st.session_state.animation_phase = current
    st.session_state.animation_last_ts = now
    return current


def safe_import_url(url: str, fallback: BikeGeometry) -> tuple[BikeGeometry, list[str]]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Adres musi zaczynać się od http:// lub https://")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Lokalne adresy są zablokowane w wersji online.")
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("Adres prowadzący do sieci prywatnej jest zablokowany.")
    except socket.gaierror as exc:
        raise ValueError("Nie można rozpoznać domeny.") from exc
    return fetch_geometry(url, fallback)


def palette(bike_type: str) -> dict[str, str]:
    kind = (bike_type or "Gravel").lower()
    if kind in ("road", "szosa"):
        return {"frame": "#58c2ff", "dark": "#2b6f9d", "halo": "#12314a", "tire": "#343941"}
    if kind in ("mtb", "mountain"):
        return {"frame": "#80e08f", "dark": "#3c8750", "halo": "#123426", "tire": "#2f3438"}
    if kind in ("trekking", "city", "urban"):
        return {"frame": "#e8c779", "dark": "#9f7d37", "halo": "#342b14", "tire": "#35393d"}
    if kind in ("tt", "triathlon"):
        return {"frame": "#ff8ca2", "dark": "#9c4e5f", "halo": "#351621", "tire": "#34383d"}
    return {"frame": "#87baff", "dark": "#426fa7", "halo": "#132b40", "tire": "#32373d"}


def render_bike_svg(
    bike: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
    phase: float,
    show_measurements: bool,
    display_scale_percent: float = 82.0,
    show_angles: bool = True,
) -> str:
    pose = calculate_pose(bike, rider, settings, phase)
    bp = bike_points(bike, settings)
    pressure = calculate_tire_pressure(rider, bike, settings)
    colors = palette(bike.bike_type)

    ground_y = bike.bb_drop - bike.wheel_radius
    xs = [bp["rear_axle"][0] - bike.wheel_radius, bp["front_axle"][0] + bike.wheel_radius]
    ys = [ground_y - 90, bike.wheel_radius + bike.bb_drop]
    for pt in (pose.hip, pose.hand, pose.saddle, pose.pedal, pose.ankle):
        xs.append(pt[0]); ys.append(pt[1])
    for pt in (pose.knee, pose.shoulder, pose.elbow):
        if pt:
            xs.append(pt[0]); ys.append(pt[1])
    if pose.shoulder:
        ys.append(pose.shoulder[1] + 180)
    min_x, max_x = min(xs) - 170, max(xs) + 170
    min_y, max_y = min(ys) - 90, max(ys) + 135
    W, H = 1120, 610
    fit_scale = min((W - 90) / (max_x - min_x), (H - 80) / (max_y - min_y))
    user_scale = max(0.60, min(1.00, float(display_scale_percent) / 100.0))
    scale = fit_scale * user_scale
    content_w = (max_x - min_x) * scale
    content_h = (max_y - min_y) * scale
    offset_x = (W - content_w) / 2.0
    offset_y = (H - content_h) / 2.0

    def T(p: tuple[float, float]) -> tuple[float, float]:
        return offset_x + (p[0] - min_x) * scale, H - offset_y - (p[1] - min_y) * scale

    def line(a, b, color, width=5, dash="", opacity=1.0):
        x1, y1 = T(a); x2, y2 = T(b)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" opacity="{opacity}"{dash_attr}/>'

    def circle(p, r, fill, stroke="none", sw=0):
        x, y = T(p)
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'

    def label(x, y, text, fill="#eef7ff", size=13, weight=600, anchor="middle"):
        return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-family="Segoe UI,Arial" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(str(text))}</text>'

    def callout(x: float, y: float, title: str, value: str, color: str, anchor: str = "middle") -> str:
        pad_x = 10
        w = max(120, 8 * max(len(title), len(value)) + 16)
        h = 38
        if anchor == "start":
            left = x
        elif anchor == "end":
            left = x - w
        else:
            left = x - w / 2
        top = y - h / 2
        txt_x = left + pad_x
        return (
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="#0f2131" opacity="0.95" stroke="{color}" stroke-width="1.6"/>'
            + label(txt_x, top + 14, title, color, 11, 800, "start")
            + label(txt_x, top + 29, value, "#f5fbff", 13, 800, "start")
        )

    parts = [
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Symulacja pozycji na rowerze">',
        '<defs><filter id="shadow"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-opacity="0.32"/></filter><marker id="arr" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M8,0 L0,4 L8,8" fill="none" stroke="#ffffff" stroke-width="1.4"/></marker></defs>',
        f'<rect width="{W}" height="{H}" rx="22" fill="#07131e"/>',
        f'<ellipse cx="{W/2:.0f}" cy="{H/2:.0f}" rx="{W*0.43:.0f}" ry="{H*0.43:.0f}" fill="{colors["halo"]}" opacity="0.78"/>',
    ]
    for gx in range(-900, 1701, 100):
        x1, y1 = T((gx, min_y)); x2, y2 = T((gx, max_y))
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#203246" stroke-width="1"/>')
    for gy in range(-400, 1301, 100):
        x1, y1 = T((min_x, gy)); x2, y2 = T((max_x, gy))
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#203246" stroke-width="1"/>')
    x1, y_ground = T((min_x, ground_y)); x2, _ = T((max_x, ground_y))
    parts.append(f'<line x1="{x1:.1f}" y1="{y_ground:.1f}" x2="{x2:.1f}" y2="{y_ground:.1f}" stroke="#617386" stroke-width="3"/>')

    for center, width_mm, bar, side in (
        (bp["rear_axle"], bike.tire_width_rear, pressure.rear_bar, "TYŁ"),
        (bp["front_axle"], bike.tire_width_front, pressure.front_bar, "PRZÓD"),
    ):
        cx, cy = T(center); rr = bike.wheel_radius * scale
        tire_w = max(6, min(15, width_mm / 4))
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr:.1f}" fill="none" stroke="{colors["tire"]}" stroke-width="{tire_w:.1f}"/>')
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr-tire_w:.1f}" fill="none" stroke="#d0dce7" stroke-width="3"/>')
        for angle in range(0, 180, 30):
            rad = math.radians(angle); dx = (rr-tire_w)*math.cos(rad); dy=(rr-tire_w)*math.sin(rad)
            parts.append(f'<line x1="{cx-dx:.1f}" y1="{cy-dy:.1f}" x2="{cx+dx:.1f}" y2="{cy+dy:.1f}" stroke="#35485a" stroke-width="1"/>')
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="#d8e1ea"/>')
        parts.append(f'<rect x="{cx-83:.1f}" y="{cy+58:.1f}" width="166" height="28" rx="9" fill="#66e1b2" opacity="0.96"/>')
        parts.append(label(cx, cy+77, f"{side}  {width_mm:.0f} mm  {bar:.2f} bar", "#07131e", 12, 800))

    for a, b in (
        (bp["rear_axle"], (0.0, 0.0)), (bp["rear_axle"], bp["seat_top"]),
        ((0.0, 0.0), bp["seat_top"]), (bp["seat_top"], bp["head_top"]),
        ((0.0, 0.0), bp["head_bottom"]), (bp["head_bottom"], bp["head_top"]),
        (bp["head_bottom"], bp["front_axle"]),
    ):
        parts.append(line(a, b, colors["dark"], 10)); parts.append(line(a, b, colors["frame"], 6))
    parts.append(line(bp["seat_top"], bp["saddle"], "#d6e2ec", 5))
    parts.append(line(bp["head_top"], bp["stem_end"], "#e2ebf3", 5))
    parts.append(line(bp["stem_end"], bp["hand"], "#e2ebf3", 5))
    sx, sy = T(bp["saddle"])
    parts.append(f'<line x1="{sx-33:.1f}" y1="{sy:.1f}" x2="{sx+31:.1f}" y2="{sy-2:.1f}" stroke="#edf3f8" stroke-width="10" stroke-linecap="round"/>')

    opposite = (-pose.pedal[0], -pose.pedal[1])
    parts.append(line((0, 0), opposite, "#708398", 4)); parts.append(line((0, 0), pose.pedal, "#67e4b5", 5))
    parts.append(circle((0, 0), 8, "#78baff")); parts.append(circle(pose.pedal, 5, "#67e4b5"))
    if pose.knee:
        parts += [line(pose.hip, pose.knee, "#f1c680", 12), line(pose.knee, pose.ankle, "#f1c680", 11), line(pose.ankle, pose.pedal, "#f1c680", 7)]
        for pt, r in ((pose.hip,8),(pose.knee,8),(pose.ankle,6)): parts.append(circle(pt,r,"#fff2d1"))
    else:
        parts.append(line(pose.hip, pose.ankle, "#ff6c84", 5, "8 6"))
    if pose.shoulder and pose.elbow:
        parts += [line(pose.hip, pose.shoulder, "#f1c680", 15), line(pose.shoulder, pose.elbow, "#f1c680", 9), line(pose.elbow, pose.hand, "#f1c680", 8)]
        for pt, r in ((pose.shoulder,8),(pose.elbow,6),(pose.hand,5)): parts.append(circle(pt,r,"#fff2d1"))
        head = (pose.shoulder[0]-12, pose.shoulder[1]+105)
        parts.append(line(pose.shoulder, (head[0], head[1]-55), "#f1c680", 7)); parts.append(circle(head, 31, "#f4c98e", "#ffe0ad", 2))

    parts.append(label(24, 28, f"{bike.name}  •  {settings.cadence:.0f} rpm  •  korba {phase:.0f}°", "#eef7ff", 15, 800, "start"))

    bb = (0.0, 0.0); saddle = bp["saddle"]; hand = bp["hand"]
    sta = math.radians(bike.seat_tube_angle)
    saddle_axis_top = (-settings.saddle_height * math.cos(sta), settings.saddle_height * math.sin(sta))
    setback = max(0.0, -saddle[0]); drop = saddle[1] - hand[1]; reach = hand[0] - saddle[0]
    mx = {"M1":"#ffd166","M2":"#57d3ff","M3":"#ff83c6","M4":"#8dea7b","M5":"#ff9f5a"}

    if show_measurements:
        bx, by = T(bb); sx2, sy2 = T(saddle); hx, hy = T(hand); px, py = T(pose.pedal)
        saxt, sayt = T(saddle_axis_top)

        def dim_line(x1, y1, x2, y2, color):
            return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="3.4" marker-start="url(#arr)" marker-end="url(#arr)"/>'

        parts.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{saxt:.1f}" y2="{sayt:.1f}" stroke="{mx["M1"]}" stroke-width="4.2" marker-start="url(#arr)" marker-end="url(#arr)"/>')
        midx = (bx + saxt) / 2 - 18; midy = (by + sayt) / 2
        parts.append(callout(midx, midy, "M1 wysokość siodła", f"{settings.saddle_height:.0f} mm po osi sztycy", mx["M1"], "end"))

        m2y = min(sy2, hy) - 64
        parts.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx:.1f}" y2="{m2y:.1f}" stroke="{mx["M2"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(f'<line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{sx2:.1f}" y2="{m2y:.1f}" stroke="{mx["M2"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(dim_line(bx, m2y, sx2, m2y, mx["M2"]))
        parts.append(callout((bx+sx2)/2, m2y-26, "M2 setback S75", f"{setback:.0f} mm za BB", mx["M2"]))

        m3x = max(sx2, hx) + 68
        parts.append(f'<line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{m3x:.1f}" y2="{sy2:.1f}" stroke="{mx["M3"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(f'<line x1="{hx:.1f}" y1="{hy:.1f}" x2="{m3x:.1f}" y2="{hy:.1f}" stroke="{mx["M3"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(dim_line(m3x, sy2, m3x, hy, mx["M3"]))
        parts.append(callout(m3x + 14, (sy2+hy)/2, "M3 drop siodło–chwyt", f"{drop:.0f} mm", mx["M3"], "start"))

        m4y = y_ground - 42
        parts.append(f'<line x1="{sx2:.1f}" y1="{sy2:.1f}" x2="{sx2:.1f}" y2="{m4y:.1f}" stroke="{mx["M4"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(f'<line x1="{hx:.1f}" y1="{hy:.1f}" x2="{hx:.1f}" y2="{m4y:.1f}" stroke="{mx["M4"]}" stroke-width="2" stroke-dasharray="7 6" opacity="0.9"/>')
        parts.append(dim_line(sx2, m4y, hx, m4y, mx["M4"]))
        parts.append(callout((sx2+hx)/2, m4y-22, "M4 reach siodło–chwyt", f"{reach:.0f} mm", mx["M4"]))

        parts.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="{mx["M5"]}" stroke-width="3.2" marker-end="url(#arr)"/>')
        parts.append(callout((bx+px)/2 + 40, (by+py)/2 + 18, "M5 długość korby", f"{bike.crank_length:.1f} mm", mx["M5"], "start"))

        for code, pt in (("BB",bb),("S75",saddle),("H",hand),("P",pose.pedal)):
            x,y=T(pt)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#f4f7fb" stroke="#07131e" stroke-width="2"/>')
            parts.append(label(x+12, y-10, code, "#f4f7fb", 11, 800, "start"))

    if show_angles:
        if pose.knee and pose.knee_flexion is not None:
            kx, ky = T(pose.knee)
            parts.append(callout(kx + 24, ky - 24, "Kąt kolana", f"{pose.knee_flexion:.1f}°", "#67e4b5", "start"))
        if pose.hip_angle is not None:
            hx0, hy0 = T(pose.hip)
            parts.append(callout(hx0 - 18, hy0 - 60, "Otwarcie biodra", f"{pose.hip_angle:.1f}°", "#7bd7ff", "end"))
        if pose.elbow and pose.elbow_angle is not None:
            ex, ey = T(pose.elbow)
            parts.append(callout(ex + 22, ey - 18, "Kąt łokcia", f"{pose.elbow_angle:.1f}°", "#ffd98a", "start"))
        if pose.shoulder and pose.torso_angle is not None:
            tx = (T(pose.shoulder)[0] + T(pose.hip)[0]) / 2
            ty = (T(pose.shoulder)[1] + T(pose.hip)[1]) / 2 - 28
            parts.append(callout(tx, ty, "Pochylenie tułowia", f"{pose.torso_angle:.1f}°", "#d6e4ff"))

    parts.append('</svg>')
    return "".join(parts)


def measurement_values(bike: BikeGeometry, settings: FitSettings) -> list[tuple[str, str, str, str]]:
    bp = bike_points(bike, settings)
    setback = max(0.0, -bp["saddle"][0])
    drop = bp["saddle"][1] - bp["hand"][1]
    reach = bp["hand"][0] - bp["saddle"][0]
    return [
        ("M1", "Wysokość po osi rury i sztycy", f"{settings.saddle_height:.0f} mm", "#ffd166"),
        ("M2", "Setback punktu S75 względem pionu BB", f"{setback:.0f} mm za BB", "#57d3ff"),
        ("M3", "Pionowy drop S75 → chwyt H", f"{drop:.0f} mm", "#ff83c6"),
        ("M4", "Poziomy reach S75 → chwyt H", f"{reach:.0f} mm", "#8dea7b"),
        ("M5", "Długość korby BB → oś pedału", f"{bike.crank_length:.1f} mm", "#ff9f5a"),
    ]


def report_html(bike: BikeGeometry, rider: Rider, settings: FitSettings) -> str:
    analysis = analyze_cycle(bike, rider, settings, samples=72)
    pressure = calculate_tire_pressure(rider, bike, settings)
    rows = "".join(f"<tr><td>{c}</td><td>{n}</td><td><b>{v}</b></td></tr>" for c,n,v,_ in measurement_values(bike,settings))
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in analysis.messages)
    return f"""<!doctype html><html lang='pl'><meta charset='utf-8'><title>Raport BikeFit</title>
    <style>body{{font-family:Arial;max-width:900px;margin:30px auto;color:#10202e}}h1{{color:#244c68}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd8e0;padding:9px}}.brand{{color:#537089}}</style>
    <h1>BikeFit Studio Online v1.6</h1><div class='brand'>Autor: MisieK</div>
    <h2>{html.escape(bike.name)}</h2><p>Rowerzysta: {html.escape(rider.name)}, wzrost {rider.height:.0f} mm, przekrok {rider.inseam:.0f} mm, masa {rider.weight:.1f} kg.</p>
    <p><b>Ocena modelu: {analysis.score:.1f}/100</b></p>
    <table><tr><th>Kod</th><th>Pomiar</th><th>Wartość</th></tr>{rows}</table>
    <h3>Kąty</h3><p>Kolano: {analysis.knee_flexion_min:.1f}–{analysis.knee_flexion_max:.1f}°. Biodro: {analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°. Łokieć: {analysis.elbow_angle:.1f}°.</p>
    <h3>Ciśnienie startowe</h3><p>Przód {pressure.front_bar:.2f} bar / {pressure.front_psi:.0f} psi; tył {pressure.rear_bar:.2f} bar / {pressure.rear_psi:.0f} psi.</p>
    <h3>Wskazówki</h3><ul>{notes}</ul>
    <p><small>Wynik jest orientacyjny i nie zastępuje profesjonalnego bike fittingu ani konsultacji medycznej.</small></p></html>"""


init_state()
apply_pending_state()

# Sidebar branding.
with st.sidebar:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=105)
    st.markdown("### BikeFit Studio Online")
    st.caption("Autor: **MisieK**")
    st.markdown("---")

    catalog = bike_catalog()
    names = [b.name for b in catalog]
    current_name = st.selectbox(
        "Wybierz rower / geometrię",
        names,
        index=names.index(st.session_state.get("selected_bike", names[0])) if st.session_state.get("selected_bike") in names else 0,
        help="Wybierz geometrię z bazy. Własne wymiary możesz wpisać poniżej.",
    )
    st.session_state.selected_bike = current_name
    base_bike = next(b for b in catalog if b.name == current_name)
    if st.session_state.get("geometry_for") != current_name:
        reset_geometry_state(base_bike)
        st.session_state.geometry_for = current_name

    with st.expander("🌐 Import geometrii z linku", expanded=True):
        st.caption("Tak jak w wersji desktopowej: otwórz katalog, wybierz dokładny model, rocznik i rozmiar, a potem wklej adres strony roweru.")
        external_link_button("Otwórz Bike Insights", "https://bikeinsights.com/search")
        external_link_button("Otwórz Geometry Geeks", "https://geometrygeeks.bike/")
        external_link_button("Otwórz 99 Spokes", "https://99spokes.com/")
        st.text_input(
            "Adres konkretnego modelu i rozmiaru",
            key="sidebar_import_url",
            placeholder="https://...",
            help="Wklej adres strony zawierającej tabelę geometrii konkretnego rozmiaru ramy.",
        )
        if st.button("Pobierz i zastosuj geometrię", key="import_geometry_sidebar", use_container_width=True, type="primary"):
            import_url = str(st.session_state.sidebar_import_url).strip()
            if not import_url:
                st.session_state.sidebar_import_status = "Wklej najpierw adres strony z geometrią."
                st.session_state.sidebar_import_notes = []
            else:
                try:
                    with st.spinner("Pobieram stronę i rozpoznaję geometrię…"):
                        imported, notes = safe_import_url(import_url, geometry_from_state(base_bike))
                    st.session_state.custom_bikes = [
                        item for item in st.session_state.custom_bikes if item.get("name") != imported.name
                    ] + [imported.to_dict()]
                    st.session_state.selected_bike = imported.name
                    reset_geometry_state(imported)
                    st.session_state.geometry_for = imported.name
                    st.session_state.sidebar_import_status = f"Zaimportowano: {imported.name}"
                    st.session_state.sidebar_import_notes = notes
                    st.rerun()
                except Exception as exc:
                    st.session_state.sidebar_import_status = f"Import nie powiódł się: {exc}"
                    st.session_state.sidebar_import_notes = []
        if st.session_state.sidebar_import_status:
            if st.session_state.sidebar_import_status.startswith("Zaimportowano"):
                st.success(st.session_state.sidebar_import_status)
            else:
                st.warning(st.session_state.sidebar_import_status)
        for import_note in st.session_state.sidebar_import_notes:
            st.caption(f"• {import_note}")

    with st.expander("📐 Ręczna edycja geometrii", expanded=False):
        st.caption("Zmiany działają od razu w symulacji. Po zapisaniu geometria pojawi się na liście wyboru w tej sesji.")
        st.text_input("Nazwa geometrii", key="geo_name")
        st.selectbox("Typ roweru", ["Gravel", "Road", "MTB", "Trekking", "City", "TT"], key="geo_type")
        quick_cols = st.columns(2)
        for i, (label_text, field, step) in enumerate(GEOMETRY_FIELDS):
            quick_cols[i % 2].number_input(label_text, key=f"geo_{field}", step=step, format="%.1f")
        if st.button("Zapisz jako własną geometrię", key="save_geometry_sidebar", use_container_width=True, type="primary"):
            edited = geometry_from_state(base_bike)
            payload = edited.to_dict()
            st.session_state.custom_bikes = [p for p in st.session_state.custom_bikes if p.get("name") != edited.name] + [payload]
            st.session_state.selected_bike = edited.name
            st.session_state.geometry_for = edited.name
            st.success("Geometria została zapisana w bieżącej sesji i dodana do listy.")
            st.rerun()

    bike = geometry_from_state(base_bike)

    st.markdown("#### Rowerzysta")
    st.text_input("Nazwa profilu", key="profile_name")
    c1, c2 = st.columns(2)
    c1.number_input("Wzrost [mm]", 1400.0, 2200.0, key="height", step=1.0)
    c2.number_input("Przekrok [mm]", 600.0, 1100.0, key="inseam", step=1.0)
    c3, c4 = st.columns(2)
    c3.number_input("Masa [kg]", 35.0, 220.0, key="weight", step=0.5)
    c4.selectbox("Mobilność", ["Ograniczona", "Średnia", "Dobra"], key="flexibility")
    st.selectbox("Charakter pozycji", ["Komfortowa", "Zrównoważona", "Sportowa"], key="style")

    rider = current_rider()
    if st.button("Dobierz ustawienie bazowe", use_container_width=True, type="primary"):
        rec = recommend_and_evaluate(rider, bike, st.session_state.style, st.session_state.flexibility)
        queue_settings(rec.settings, rec.notes)
        st.rerun()

    if st.button("Optymalizuj aktualne ustawienie", use_container_width=True):
        with st.spinner("Analizuję pełny obrót korby…"):
            result, analysis = optimize_fit(bike, rider, current_settings())
        queue_settings(result, [f"Optymalizacja zakończona wynikiem {analysis.score:.1f}/100."])
        st.rerun()

    st.markdown("#### Regulacja")
    st.slider("M1 wysokość siodła [mm]", 620.0, 850.0, key="saddle_height", step=1.0)
    st.slider("Regulacja siodła na szynach [mm]", -60.0, 80.0, key="saddle_fore_aft", step=1.0)
    st.slider("Zmiana wysokości kierownicy [mm]", -60.0, 100.0, key="handlebar_stack_delta", step=1.0)
    st.slider("Zmiana zasięgu kierownicy [mm]", -80.0, 80.0, key="handlebar_reach_delta", step=1.0)
    st.slider("Kadencja [rpm]", 40.0, 130.0, key="cadence", step=1.0)
    st.slider("Kąt stopy [°]", -20.0, 15.0, key="foot_angle", step=1.0)
    st.slider("Pozycja korby [°]", 0.0, 359.0, key="phase", step=1.0)
    st.checkbox("Animacja korby wg kadencji", key="animate_crank", help="Po włączeniu korba obraca się automatycznie z prędkością wynikającą z kadencji.")
    st.checkbox("Pokaż kąty na rysunku", key="show_angles")
    st.slider("Skala symulacji [%]", 65.0, 100.0, key="simulation_scale", step=1.0, help="Zmniejsz, aby cały rower i rowerzysta mieścili się wygodniej na ekranie.")
    st.checkbox("Pokaż wymiary M1–M5", key="show_measurements")

settings = current_settings()
rider = current_rider()
analysis = analyze_cycle(bike, rider, settings, samples=72)
pressure = calculate_tire_pressure(rider, bike, settings)

st.markdown("""
<div class="hero">
  <h1>BikeFit Studio Online v1.6</h1>
  <p>Interaktywny konfigurator pozycji, wymiarów roweru i ciśnienia w oponach — bez instalowania programu.</p>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Ocena ustawienia</div><div class="metric-value">{analysis.score:.0f}/100</div><div class="metric-note">model biomechaniczny 2D</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Zakres kolana</div><div class="metric-value">{analysis.knee_flexion_min:.1f}–{analysis.knee_flexion_max:.1f}°</div><div class="metric-note">pełny obrót korby</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Ciśnienie przód</div><div class="metric-value">{pressure.front_bar:.2f} bar</div><div class="metric-note">{pressure.front_psi:.0f} psi</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Ciśnienie tył</div><div class="metric-value">{pressure.rear_bar:.2f} bar</div><div class="metric-note">{pressure.rear_psi:.0f} psi</div></div>', unsafe_allow_html=True)

main_tab, config_tab, tire_tab, geometry_tab, import_tab, report_tab = st.tabs([
    "Symulacja", "Wymiary i konfigurator", "Opony i ciśnienie", "Geometria roweru", "Import online", "Raport",
])

with main_tab:
    def _render_simulation_block() -> None:
        phase_to_draw = display_phase_deg()
        st.markdown(
            render_bike_svg(
                bike,
                rider,
                settings,
                phase_to_draw,
                bool(st.session_state.show_measurements),
                float(st.session_state.simulation_scale),
                bool(st.session_state.show_angles),
            ),
            unsafe_allow_html=True,
        )

    if hasattr(st, "fragment"):
        @st.fragment(run_every="250ms")
        def live_simulation_fragment() -> None:
            _render_simulation_block()

        live_simulation_fragment()
    else:
        _render_simulation_block()

    cards = "".join(
        f'<div class="measure-card"><div class="measure-code" style="color:{color}">{code}</div><div class="measure-name">{name}</div><div class="measure-value">{value}</div></div>'
        for code, name, value, color in measurement_values(bike, settings)
    )
    st.markdown(f'<div class="measure-grid">{cards}</div>', unsafe_allow_html=True)

    a1, a2, a3, a4 = st.columns(4)
    a1.info(f"**Kolano:** {analysis.knee_flexion_min:.1f}–{analysis.knee_flexion_max:.1f}°")
    a2.info(f"**Biodro:** {analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°")
    a3.info(f"**Łokieć:** {analysis.elbow_angle:.1f}°")
    a4.info(f"**Tułów:** {analysis.torso_angle:.1f}°")

    st.info("S75 oznacza środek siodła w miejscu, w którym siodło ma 75 mm szerokości. Na rysunku M1–M4 to główne wartości do ustawienia na realnym rowerze. Włącz animację, aby obserwować pełny ruch przy zadanej kadencji.")

with config_tab:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Aktualne ustawienie")
        st.write(f"**Wysokość siodła:** {settings.saddle_height:.0f} mm")
        st.write(f"**Regulacja na szynach:** {settings.saddle_fore_aft:+.0f} mm")
        st.write(f"**Kierownica — wysokość:** {settings.handlebar_stack_delta:+.0f} mm")
        st.write(f"**Kierownica — zasięg:** {settings.handlebar_reach_delta:+.0f} mm")
        st.write(f"**Pochylenie tułowia:** {analysis.torso_angle:.1f}°")
        st.write(f"**Kąt łokcia:** {analysis.elbow_angle:.1f}°")
        st.write(f"**Zakres biodra:** {analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°")
    with right:
        st.subheader("Wskazówki modelu")
        for note in analysis.messages:
            st.write(f"• {note}")
        for note in st.session_state.fit_notes:
            st.write(f"• {note}")
        st.warning("Wprowadzaj zmiany na prawdziwym rowerze stopniowo, zwykle po 2–5 mm, i testuj każdą zmianę podczas jazdy.")
    st.subheader("Jak zmierzyć samą metrówką")
    for line in measurement_guide(bike, settings):
        st.write(f"• {line}")

with tire_tab:
    c1, c2, c3 = st.columns(3)
    c1.number_input("Masa roweru [kg]", 4.0, 40.0, key="geo_bike_weight", step=0.1)
    c2.number_input("Bagaż / wyposażenie [kg]", 0.0, 40.0, key="gear_weight", step=0.1)
    c3.slider("Obciążenie przodu [%]", 35.0, 50.0, key="front_load_percent", step=0.5)
    c4, c5, c6 = st.columns(3)
    c4.number_input("Szerokość opony przód [mm]", 20.0, 80.0, key="geo_tire_width_front", step=1.0)
    c5.number_input("Szerokość opony tył [mm]", 20.0, 80.0, key="geo_tire_width_rear", step=1.0)
    c6.number_input("Limit opony/obręczy [bar]", 1.5, 9.0, key="geo_tire_max_pressure", step=0.1)
    d1, d2 = st.columns(2)
    d1.selectbox("System", list(SETUP_FACTORS), key="tire_setup")
    d1.selectbox("Nawierzchnia", list(SURFACE_FACTORS), key="tire_surface")
    d2.selectbox("Oplot", list(CASING_FACTORS), key="tire_casing")
    d2.selectbox("Priorytet", list(GOAL_OFFSETS_BAR), key="pressure_goal")
    bike = geometry_from_state(base_bike)
    settings = current_settings(); pressure = calculate_tire_pressure(rider, bike, settings)
    p1, p2 = st.columns(2)
    p1.metric("Przód", f"{pressure.front_bar:.2f} bar", f"{pressure.front_psi:.0f} psi")
    p2.metric("Tył", f"{pressure.rear_bar:.2f} bar", f"{pressure.rear_psi:.0f} psi")
    st.write(f"Zakres testowy przód: **{pressure.front_low:.2f}–{pressure.front_high:.2f} bar**")
    st.write(f"Zakres testowy tył: **{pressure.rear_low:.2f}–{pressure.rear_high:.2f} bar**")
    st.info(pressure.warning)
    if st.button("Ustaw sugerowany rozkład masy"):
        st.session_state.front_load_percent = suggested_front_load_percent(bike.bike_type, settings.style)
        st.rerun()

with geometry_tab:
    st.subheader("Geometria aktywnego roweru")
    st.info("Import z linku i ręczna edycja geometrii znajdują się w panelu po lewej: **🌐 Import geometrii z linku** oraz **📐 Ręczna edycja geometrii**. Zmiany są widoczne w symulacji natychmiast.")
    active_geometry = geometry_from_state(base_bike)
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Stack", f"{active_geometry.stack:.1f} mm")
    g2.metric("Reach", f"{active_geometry.reach:.1f} mm")
    g3.metric("Kąt rury podsiodłowej", f"{active_geometry.seat_tube_angle:.1f}°")
    g4.metric("Rozstaw osi", f"{active_geometry.wheelbase:.1f} mm")

    st.markdown("#### Wszystkie aktywne wymiary")
    table_rows = "".join(
        f"<tr><td style='padding:7px 10px;border-bottom:1px solid #2d4357'>{html.escape(label_text)}</td><td style='padding:7px 10px;border-bottom:1px solid #2d4357'><b>{getattr(active_geometry, field):.1f}</b></td></tr>"
        for label_text, field, _step in GEOMETRY_FIELDS
    )
    st.markdown(
        f'<div class="info-card"><table style="width:100%;border-collapse:collapse;color:#eef7ff">{table_rows}</table></div>',
        unsafe_allow_html=True,
    )
    profile_json = json.dumps(active_geometry.to_dict(), ensure_ascii=False, indent=2)
    st.download_button(
        "Pobierz geometrię JSON",
        data=profile_json,
        file_name="geometria_roweru.json",
        mime="application/json",
        use_container_width=True,
    )

with import_tab:
    st.subheader("Import geometrii z internetu")
    st.write("Otwórz katalog, wybierz model, rocznik i rozmiar, a następnie wklej adres konkretnej strony roweru.")
    l1, l2, l3 = st.columns(3)
    with l1:
        external_link_button("Bike Insights", "https://bikeinsights.com/search")
    with l2:
        external_link_button("Geometry Geeks", "https://geometrygeeks.bike/")
    with l3:
        external_link_button("99 Spokes", "https://99spokes.com/")
    url = st.text_input("Adres strony z geometrią", placeholder="https://...")
    if st.button("Pobierz i rozpoznaj geometrię", type="primary"):
        if not url:
            st.error("Wklej adres strony.")
        else:
            try:
                with st.spinner("Pobieram stronę i rozpoznaję parametry…"):
                    imported, notes = safe_import_url(url, bike)
                st.session_state.custom_bikes = [p for p in st.session_state.custom_bikes if p.get("name") != imported.name] + [imported.to_dict()]
                st.session_state.selected_bike = imported.name
                reset_geometry_state(imported)
                st.session_state.geometry_for = imported.name
                st.success("Import zakończony. Sprawdź wartości w zakładce „Geometria roweru”.")
                for note in notes:
                    st.write(f"• {note}")
            except Exception as exc:
                st.error(f"Import nie powiódł się: {exc}")
    st.caption("Niektóre strony blokują automatyczny odczyt. W takim przypadku przepisz wartości w zakładce geometrii.")

with report_tab:
    st.subheader("Zapis profilu i raport")
    profile = {
        "bike": bike.to_dict(),
        "rider": rider.to_dict(),
        "settings": settings.to_dict(),
    }
    st.download_button(
        "Pobierz profil JSON",
        data=json.dumps(profile, ensure_ascii=False, indent=2),
        file_name="profil_bikefit.json",
        mime="application/json",
        use_container_width=True,
    )
    st.download_button(
        "Pobierz raport HTML",
        data=report_html(bike, rider, settings),
        file_name="raport_bikefit.html",
        mime="text/html",
        use_container_width=True,
    )
    upload = st.file_uploader("Wczytaj zapisany profil JSON", type=["json"])
    if upload is not None and st.button("Zastosuj wczytany profil"):
        try:
            payload = json.load(upload)
            imported_bike = BikeGeometry.from_dict(payload.get("bike", {}))
            imported_rider = Rider.from_dict(payload.get("rider", {}))
            imported_settings = FitSettings.from_dict(payload.get("settings", {}))
            st.session_state.custom_bikes = [p for p in st.session_state.custom_bikes if p.get("name") != imported_bike.name] + [imported_bike.to_dict()]
            st.session_state.selected_bike = imported_bike.name
            reset_geometry_state(imported_bike)
            st.session_state.geometry_for = imported_bike.name
            st.session_state.profile_name = imported_rider.name
            st.session_state.height = imported_rider.height
            st.session_state.inseam = imported_rider.inseam
            st.session_state.weight = imported_rider.weight
            st.session_state.flexibility = imported_rider.flexibility
            apply_settings(imported_settings)
            st.rerun()
        except Exception as exc:
            st.error(f"Nie udało się wczytać profilu: {exc}")

st.markdown("""
<div class="footer-note">BikeFit Studio Online • autor: MisieK • narzędzie orientacyjne, nie wyrób medyczny</div>
""", unsafe_allow_html=True)
