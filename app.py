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
import streamlit.components.v1 as components

from bikefit.diagnostics import FitDiagnostic, explain_fit
from bikefit.frame_size import FrameSizeAssessment, assess_frame_size
from bikefit.internet_import import fetch_geometry
from bikefit.kinematics import analyze_cycle, bike_points, calculate_pose
from bikefit.models import BikeGeometry, FitSettings, Rider
from bikefit.optimizer import optimize_fit
from bikefit.shared_store import (
    GeometryStoreConfig,
    SharedStoreError,
    build_store_document,
    config_from_mapping,
    delete_local_geometry_file,
    delete_remote_bike,
    load_local_geometry_folder,
    load_remote_bikes,
    merge_bike_payloads,
    parse_store_document,
    save_local_geometry_file,
    save_remote_bike,
)
from bikefit.recommendations import measurement_guide, recommend_and_evaluate
from bikefit.visitor_counter import CounterError, request_counter
from bikefit.visual_guides import build_visual_measurement_guides_html
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
COMMUNITY_BIKES_FILE = ROOT / "data" / "community_bikes.json"
COMMUNITY_BIKES_DIR = ROOT / "data" / "user_geometries"
LOGO_FILE = ROOT / "assets" / "logo_misiek.png"
COUNTER_NAMESPACE = "misiek-bikefit-studio-online"
COUNTER_API_BASE = "https://api.counterapi.dev/v1"

st.set_page_config(
    page_title="BikeFit Studio Online v4.5 — MisieK",
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
.measure-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:8px 0 14px;}
.measure-card {padding:12px;border-radius:14px;background:#101f2d;border:1px solid #314b61;}
.measure-code {font-weight:900;font-size:1rem;}
.measure-name {color:#b8cad9;font-size:.78rem;min-height:34px;margin-top:4px;}
.measure-value {color:#f8fbff;font-size:1.1rem;font-weight:800;margin-top:5px;}
.frame-size-card {padding:16px 18px;border-radius:16px;background:#10202e;border:1px solid #35536b;margin:12px 0 16px;}
.frame-size-head {display:flex;align-items:center;gap:10px;margin-bottom:7px;}
.frame-size-badge {display:inline-flex;padding:5px 10px;border-radius:999px;font-size:.77rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;background:#162b3d;}
.frame-size-title {font-size:1.15rem;font-weight:850;color:#f5fbff;}
.frame-size-summary {color:#c2d2df;line-height:1.5;margin:6px 0;}
.frame-size-reason {color:#a9bdcd;margin:4px 0;line-height:1.4;}
.frame-size-suggestion {margin-top:10px;padding:10px 12px;border-radius:10px;background:#0b1823;color:#eef7ff;border-left:4px solid currentColor;}
.geometry-store-warning {padding:10px 12px;border-radius:12px;background:#392b12;border:1px solid #7c6222;color:#ffe7a3;margin:8px 0;line-height:1.4;}
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
[data-testid="stTabs"] button {color:#a9bed0 !important;opacity:1 !important;font-weight:650 !important;pointer-events:auto !important;cursor:pointer !important;}
[data-testid="stTabs"] button:hover {color:#ffffff !important;}
[data-testid="stTabs"] button[aria-selected="true"] {color:#ffffff !important;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background:#67e4b5 !important;}

[data-testid="stMetricValue"] {color:#f6fbff;}
[data-testid="stMetricLabel"] {color:#a9bed0;}

/* Szerszy, czytelniejszy panel boczny. */
[data-testid="stSidebar"] {
  min-width:330px !important;
  width:330px !important;
}
[data-testid="stSidebar"] > div:first-child {
  width:330px !important;
}
[data-testid="stSidebar"] .stButton > button {
  min-height:42px !important;
  white-space:normal !important;
  line-height:1.2 !important;
  padding:0.55rem 0.65rem !important;
}

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
/* Wszystkie przyciski w aplikacji — ciemne tło zamiast białego. */
.stButton > button,
.stDownloadButton > button,
button[data-testid="stBaseButton-secondary"],
button[kind="secondary"] {
  background:#173047 !important;
  color:#ffffff !important;
  border:1px solid #466985 !important;
  border-radius:12px !important;
  font-weight:700 !important;
  box-shadow:none !important;
}
.stButton > button p,
.stButton > button span,
.stDownloadButton > button p,
.stDownloadButton > button span,
button[data-testid="stBaseButton-secondary"] p,
button[data-testid="stBaseButton-secondary"] span {
  color:#ffffff !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
button[data-testid="stBaseButton-secondary"]:hover,
button[kind="secondary"]:hover {
  background:#214661 !important;
  color:#ffffff !important;
  border-color:#6d9abc !important;
}
.stButton > button:focus,
.stDownloadButton > button:focus,
button[data-testid="stBaseButton-secondary"]:focus {
  outline:2px solid #67e4b5 !important;
  outline-offset:2px !important;
  box-shadow:none !important;
}
button[data-testid="stBaseButton-primary"],
button[kind="primary"] {
  background:#2f8f72 !important;
  color:#ffffff !important;
  border:1px solid #67e4b5 !important;
  border-radius:12px !important;
  font-weight:800 !important;
}
button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primary"] span,
button[kind="primary"] p,
button[kind="primary"] span {
  color:#ffffff !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover {
  background:#3ba886 !important;
  border-color:#8ff2cd !important;
}
.stButton > button:disabled,
.stDownloadButton > button:disabled,
button[data-testid="stBaseButton-secondary"]:disabled,
button[data-testid="stBaseButton-primary"]:disabled {
  background:#263746 !important;
  color:#8195a7 !important;
  border-color:#3c5062 !important;
  opacity:1 !important;
}

/* Zawartość zakładek zawsze aktywna i czytelna, także po animacji/odświeżeniu. */
[data-testid="stTabs"] [role="tabpanel"] {
  color:#eef7ff !important;
  opacity:1 !important;
  pointer-events:auto !important;
}
[data-testid="stTabs"] [role="tabpanel"] [data-stale="true"] {opacity:1 !important;}
[data-testid="stTabs"] [role="tabpanel"] h1,
[data-testid="stTabs"] [role="tabpanel"] h2,
[data-testid="stTabs"] [role="tabpanel"] h3,
[data-testid="stTabs"] [role="tabpanel"] h4,
[data-testid="stTabs"] [role="tabpanel"] p,
[data-testid="stTabs"] [role="tabpanel"] li,
[data-testid="stTabs"] [role="tabpanel"] strong,
[data-testid="stTabs"] [role="tabpanel"] [data-testid="stMarkdownContainer"] {
  color:#eef7ff !important;
  opacity:1 !important;
}
.config-grid {display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:12px 0 18px;}
.config-card {background:#10202e;border:1px solid #345269;border-radius:16px;padding:18px;color:#eef7ff;}
.config-card h3 {color:#f5fbff !important;margin:0 0 12px;font-size:1.25rem;}
.config-row {display:flex;justify-content:space-between;gap:20px;padding:8px 0;border-bottom:1px solid #263d50;color:#b8cad9;}
.config-row:last-child {border-bottom:0;}
.config-row b {color:#ffffff !important;white-space:nowrap;}
.config-note {padding:8px 0;color:#d8e7f3;line-height:1.45;}
.config-warning {background:#2b2a16;border:1px solid #75661d;color:#ffd54f;padding:14px 16px;border-radius:13px;margin-top:12px;line-height:1.45;}
.fit-diagnostic-wrap {margin:14px 0 18px;padding:18px;border-radius:18px;background:linear-gradient(145deg,#172535,#0d1b28);border:1px solid #4a6275;}
.fit-diagnostic-wrap.bad {border-color:#b96852;background:linear-gradient(145deg,#2d1d20,#121b25);}
.fit-diagnostic-wrap.good {border-color:#2e8a6b;background:linear-gradient(145deg,#123128,#0e2024);}
.fit-diagnostic-title {font-size:1.25rem;font-weight:900;color:#f7fbff;margin-bottom:5px;}
.fit-diagnostic-summary {color:#b9cad8;line-height:1.45;margin-bottom:12px;}
.fit-diagnostic-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;}
.fit-diagnostic-item {background:#10202e;border:1px solid #3b556b;border-left:5px solid #ffd166;border-radius:14px;padding:14px 15px;color:#edf7ff;}
.fit-diagnostic-item.critical {border-left-color:#ff6c84;background:#291b23;}
.fit-diagnostic-item.warning {border-left-color:#ffd166;}
.fit-diagnostic-item.info {border-left-color:#67e4b5;}
.fit-diagnostic-area {font-size:.76rem;text-transform:uppercase;letter-spacing:.07em;color:#9fb5c7;font-weight:800;}
.fit-diagnostic-item h4 {margin:5px 0 7px;color:#ffffff !important;font-size:1.03rem;}
.fit-diagnostic-measured {display:inline-block;margin:2px 0 9px;padding:5px 8px;border-radius:8px;background:#081521;color:#9fddff;font-weight:800;font-size:.85rem;}
.fit-diagnostic-line {margin:6px 0;color:#d8e7f3;line-height:1.45;}
.fit-diagnostic-line b {color:#ffffff;}
.fit-diagnostic-correction {margin-top:9px;padding:9px 10px;border-radius:9px;background:#15352d;color:#8ff1cc;line-height:1.4;font-weight:700;}
.measure-help {background:#0f1e2b;border:1px solid #304d64;border-radius:16px;padding:18px;margin-top:14px;color:#e7f3fc;}
.measure-help h3 {color:#f5fbff !important;margin-top:0;}
.measure-help div {padding:7px 0;border-bottom:1px solid #263d50;color:#d8e7f3;}
.measure-help div:last-child {border-bottom:0;}
@media (max-width: 900px) {.config-grid{grid-template-columns:1fr}}

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


def render_visitor_counter() -> None:
    # Każdy licznik ma osobną flagę, więc częściowa awaria nie zawyża sumy.
    day_key = time.strftime("visits-%Y%m%d")
    try:
        if not bool(st.session_state.get("visitor_total_recorded", False)):
            st.session_state.visitor_counter_total = request_counter(
                COUNTER_API_BASE, COUNTER_NAMESPACE, "visits", increment=True
            )
            st.session_state.visitor_total_recorded = True
        if not bool(st.session_state.get("visitor_today_recorded", False)):
            st.session_state.visitor_counter_today = request_counter(
                COUNTER_API_BASE, COUNTER_NAMESPACE, day_key, increment=True
            )
            st.session_state.visitor_today_recorded = True

        total = int(st.session_state.get("visitor_counter_total", 0))
        today = int(st.session_state.get("visitor_counter_today", 0))
        total_text = f"{total:,}".replace(",", " ")
        today_text = f"{today:,}".replace(",", " ")
        counter_html = (
            '<div style="display:flex;justify-content:center;margin-top:12px">'
            '<div style="display:inline-flex;gap:9px;align-items:center;padding:8px 14px;border-radius:999px;'
            'background:#102131;border:1px solid #35536b;color:#eaf5ff;font-size:.82rem">'
            f'👥 Odwiedziny: <b style="color:#67e4b5;font-size:.95rem">{total_text}</b>'
            f'<span style="color:#9db3c7">• dzisiaj: {today_text}</span></div></div>'
        )
        st.markdown(counter_html, unsafe_allow_html=True)
    except CounterError:
        return


@st.cache_data(ttl=60, show_spinner=False)
def load_remote_shared_bikes_cached(
    owner: str, repo: str, branch: str, store_path: str, _token: str
) -> list[dict[str, object]]:
    config = GeometryStoreConfig(
        token=_token, owner=owner, repo=repo, branch=branch, path=store_path
    )
    bikes, _sha = load_remote_bikes(config)
    return bikes


@st.cache_data(ttl=15, show_spinner=False)
def load_local_shared_bikes_cached(folder_text: str, legacy_text: str) -> list[dict[str, object]]:
    return load_local_geometry_folder(Path(folder_text), Path(legacy_text))


def geometry_store_config() -> GeometryStoreConfig | None:
    try:
        section = st.secrets.get("geometry_store", {})
    except Exception:
        return None
    return config_from_mapping(section)


def load_shared_geometry_payloads() -> tuple[list[dict[str, object]], bool, str]:
    """Zwraca wspólne geometrie, informację o trwałości i krótki status."""
    config = geometry_store_config()
    if config is not None:
        try:
            bikes = load_remote_shared_bikes_cached(
                config.owner, config.repo, config.branch, config.path, config.token
            )
            label = "Trwały folder online" if config.folder_mode else "Wspólna baza online"
            return bikes, True, f"{label}: {len(bikes)} geometrii"
        except SharedStoreError:
            # Awaria zewnętrznego magazynu nie może zatrzymać konfiguratora.
            local = load_local_shared_bikes_cached(str(COMMUNITY_BIKES_DIR), str(COMMUNITY_BIKES_FILE))
            return local, False, "Wspólna baza chwilowo niedostępna — używam kopii lokalnej"
    local = load_local_shared_bikes_cached(str(COMMUNITY_BIKES_DIR), str(COMMUNITY_BIKES_FILE))
    return local, False, f"Baza lokalna: {len(local)} geometrii"


def persist_shared_geometry(bike: BikeGeometry, saved_by: str) -> tuple[bool, str]:
    """Zapisuje geometrię do wspólnej bazy, bez ujawniania backendu w UI."""
    payload = bike.to_dict()
    config = geometry_store_config()
    try:
        if config is not None:
            save_remote_bike(config, payload, saved_by=saved_by)
            load_remote_shared_bikes_cached.clear()
            if config.folder_mode:
                return True, "Geometria została zapisana jako osobny plik w trwałym folderze i będzie widoczna dla innych osób."
            return True, "Geometria została zapisana we wspólnej bazie i będzie widoczna dla innych osób."
        save_local_geometry_file(COMMUNITY_BIKES_DIR, payload, saved_by=saved_by)
        load_local_shared_bikes_cached.clear()
        return False, "Geometria została zapisana na bieżącym serwerze. Włącz trwałą wspólną bazę, aby zachować ją po ponownym wdrożeniu."
    except (SharedStoreError, OSError) as exc:
        # Zawsze zachowujemy ją co najmniej w sesji użytkownika.
        return False, f"Geometria pozostała w tej sesji, ale wspólny zapis nie powiódł się: {exc}"


def remember_geometry_in_session(bike: BikeGeometry) -> None:
    payload = bike.to_dict()
    key = bike.name.casefold()
    st.session_state.custom_bikes = [
        item for item in st.session_state.custom_bikes
        if str(item.get("name", "")).casefold() != key
    ] + [payload]

def delete_shared_geometry(bike_name: str) -> tuple[bool, str]:
    """Usuwa własną geometrię z bazy online/lokalnej i z bieżącej sesji."""
    key = bike_name.casefold()
    st.session_state.custom_bikes = [
        item for item in st.session_state.custom_bikes
        if str(item.get("name", "")).casefold() != key
    ]
    config = geometry_store_config()
    try:
        if config is not None:
            removed = delete_remote_bike(config, bike_name)
            load_remote_shared_bikes_cached.clear()
            if removed:
                return True, f"Usunięto geometrię: {bike_name}"
            return False, "Nie znaleziono tej geometrii w trwałej bazie."
        removed = delete_local_geometry_file(
            COMMUNITY_BIKES_DIR, bike_name, legacy_file=COMMUNITY_BIKES_FILE
        )
        load_local_shared_bikes_cached.clear()
        if removed:
            return True, f"Usunięto lokalną geometrię: {bike_name}"
        return False, "Nie znaleziono tej geometrii w bazie lokalnej."
    except (SharedStoreError, OSError) as exc:
        return False, f"Nie udało się usunąć geometrii: {exc}"


def clean_geometry_name(value: object, fallback: str = "Nowa geometria") -> str:
    """Zwraca krótką, czytelną nazwę geometrii do wspólnej bazy."""
    name = " ".join(str(value or "").strip().split())
    if not name:
        name = " ".join(str(fallback or "Nowa geometria").strip().split())
    # Chroni listę wyboru przed bardzo długimi tytułami stron lub pełnymi URL-ami.
    return name[:120]


def imported_geometry_with_name(payload: dict[str, object], name: object) -> BikeGeometry:
    bike = BikeGeometry.from_dict(payload)
    return replace(bike, name=clean_geometry_name(name, bike.name))


def external_link_button(label: str, url: str) -> None:
    """Renderuje niezawodny ciemny przycisk-link niezależny od motywu Streamlit."""
    safe_label = html.escape(label)
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f'<a class="external-link-btn" href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>',
        unsafe_allow_html=True,
    )


def render_fit_diagnostics(diagnostics: list[FitDiagnostic], score: float) -> str:
    if score >= 90.0:
        return (
            '<section class="fit-diagnostic-wrap good">'
            '<div class="fit-diagnostic-title">✓ Ustawienie mieści się w dobrym zakresie modelu</div>'
            f'<div class="fit-diagnostic-summary">Ocena {score:.1f}/100. Podstawowe kąty nie przekraczają progów wymagających ostrzeżenia. '
            'Dalsze korekty wprowadzaj tylko małymi krokami i oceniaj je podczas jazdy.</div>'
            '</section>'
        )

    cards = []
    for item in diagnostics:
        cards.append(
            f'<article class="fit-diagnostic-item {html.escape(item.severity)}">'
            f'<div class="fit-diagnostic-area">{html.escape(item.area)}</div>'
            f'<h4>{html.escape(item.title)}</h4>'
            f'<div class="fit-diagnostic-measured">{html.escape(item.measured)}</div>'
            f'<div class="fit-diagnostic-line"><b>Dlaczego to jest nieprawidłowe:</b> {html.escape(item.why)}</div>'
            f'<div class="fit-diagnostic-line"><b>Co może się dziać podczas jazdy:</b> {html.escape(item.possible_effect)}</div>'
            f'<div class="fit-diagnostic-correction">Korekta: {html.escape(item.correction)}</div>'
            '</article>'
        )
    cards_html = ''.join(cards) or (
        '<article class="fit-diagnostic-item warning"><h4>Pozycja wymaga korekty</h4>'
        '<div class="fit-diagnostic-line">Model wykrył łączne odchylenie kilku parametrów. Cofnij ostatnią zmianę suwaka i sprawdź wynik ponownie.</div></article>'
    )
    return (
        '<section class="fit-diagnostic-wrap bad">'
        '<div class="fit-diagnostic-title">Dlaczego to ustawienie będzie nieprawidłowe?</div>'
        f'<div class="fit-diagnostic-summary">Ocena spadła do {score:.1f}/100. Poniżej 90/100 program pokazuje najbardziej prawdopodobne przyczyny, ich wpływ na pozycję i kierunek korekty.</div>'
        f'<div class="fit-diagnostic-grid">{cards_html}</div>'
        '</section>'
    )


def render_frame_size_assessment(result: FrameSizeAssessment, compact: bool = False) -> str:
    reasons = "".join(
        f'<div class="frame-size-reason">• {html.escape(reason)}</div>'
        for reason in result.reasons
    )
    confidence = f"Pewność oceny: {html.escape(result.confidence)}"
    compact_class = ' style="margin:8px 0 12px"' if compact else ""
    return (
        f'<section class="frame-size-card"{compact_class}>'
        f'<div class="frame-size-head"><span class="frame-size-badge" style="color:{result.color};border:1px solid {result.color}">ROZMIAR RAMY</span>'
        f'<div class="frame-size-title">{html.escape(result.title)}</div></div>'
        f'<div class="frame-size-summary">{html.escape(result.summary)}</div>'
        f'{reasons}'
        f'<div class="frame-size-suggestion" style="color:{result.color}"><b>Co sprawdzić:</b> '
        f'<span style="color:#eef7ff">{html.escape(result.suggestion)}</span></div>'
        f'<div class="small-muted" style="margin-top:8px">{confidence}. Ocena jest orientacyjna i nie zastępuje tabeli rozmiarów producenta.</div>'
        '</section>'
    )


def geometry_backup_payloads() -> list[dict[str, object]]:
    """Łączy wspólną bazę i geometrie z bieżącej sesji do kopii bezpieczeństwa."""
    shared, _persistent, _status = load_shared_geometry_payloads()
    merged: list[dict[str, object]] = []
    for payload in [*shared, *st.session_state.get("custom_bikes", [])]:
        if isinstance(payload, dict):
            merged = merge_bike_payloads(merged, payload)
    return merged


def geometry_backup_bytes() -> bytes:
    return build_store_document(
        geometry_backup_payloads(),
        saved_by=str(st.session_state.get("user_alias", "")),
    )


FIT_VALUE_LIMITS: dict[str, tuple[float, float]] = {
    "height": (1400.0, 2200.0),
    "inseam": (600.0, 1100.0),
    "weight": (35.0, 220.0),
    "saddle_height": (500.0, 900.0),
    "saddle_fore_aft": (-60.0, 80.0),
    "handlebar_stack_delta": (-60.0, 100.0),
    "handlebar_reach_delta": (-80.0, 80.0),
    "cadence": (40.0, 130.0),
    "foot_angle": (-20.0, 15.0),
    "gear_weight": (0.0, 40.0),
    "front_load_percent": (35.0, 50.0),
    "phase": (0.0, 359.0),
    "simulation_scale": (65.0, 100.0),
    "animation_speed": (0.25, 2.0),
}


def clamp_number(value: object, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
        if not math.isfinite(number):
            return fallback
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def sanitize_numeric_state() -> None:
    """Naprawia stare, błędne lub zaimportowane wartości przed utworzeniem widżetów."""
    defaults = {
        "height": 1750.0,
        "inseam": 810.0,
        "weight": 75.0,
        "saddle_height": 715.0,
        "saddle_fore_aft": 0.0,
        "handlebar_stack_delta": 0.0,
        "handlebar_reach_delta": 0.0,
        "cadence": 85.0,
        "foot_angle": -8.0,
        "gear_weight": 1.5,
        "front_load_percent": 44.0,
        "phase": 270.0,
        "simulation_scale": 82.0,
        "animation_speed": 1.0,
    }
    for key, (low, high) in FIT_VALUE_LIMITS.items():
        st.session_state[key] = clamp_number(
            st.session_state.get(key, defaults[key]), low, high, defaults[key]
        )


def sanitize_fit_settings(settings: FitSettings) -> FitSettings:
    """Ogranicza wynik algorytmu do zakresów obsługiwanych przez interfejs."""
    return replace(
        settings,
        saddle_height=clamp_number(settings.saddle_height, 500.0, 900.0, 715.0),
        saddle_fore_aft=clamp_number(settings.saddle_fore_aft, -60.0, 80.0, 0.0),
        handlebar_stack_delta=clamp_number(settings.handlebar_stack_delta, -60.0, 100.0, 0.0),
        handlebar_reach_delta=clamp_number(settings.handlebar_reach_delta, -80.0, 80.0, 0.0),
        cadence=clamp_number(settings.cadence, 40.0, 130.0, 85.0),
        foot_angle=clamp_number(settings.foot_angle, -20.0, 15.0, -8.0),
        gear_weight=clamp_number(settings.gear_weight, 0.0, 40.0, 1.5),
        front_load_percent=clamp_number(settings.front_load_percent, 35.0, 50.0, 44.0),
    )


def init_state() -> None:
    defaults = {
        "profile_name": "Rowerzysta",
        "height": 1750.0,
        "inseam": 810.0,
        "weight": 75.0,
        "flexibility": "Średnia",
        "style": "Zrównoważona",
        "saddle_height": 715.0,
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
        "animation_speed": 1.0,
        "auto_inseam": False,
        "user_logged_in": False,
        "user_alias": "",
        "fit_notes": [],
        "custom_bikes": [],
        "selected_bike": "Gravel M — przykład",
        "shared_store_status": "",
        "shared_store_persistent": False,
        "sidebar_import_url": "",
        "sidebar_import_status": "",
        "sidebar_import_notes": [],
        "sidebar_import_custom_name": "",
        "sidebar_import_preview_name": "",
        "pending_import_geometry": None,
        "pending_import_notes": [],
        "fit_action_status": "",
        "fit_action_error": False,
        "pending_profile_payload": None,
        "geometry_action_status": "",
        "geometry_action_error": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def estimate_inseam_from_height(height_mm: float) -> float:
    """Orientacyjny przekrok dla osób, które go nie znają.

    Współczynnik 0,465 daje rozsądny punkt startowy dla konfiguratora,
    ale nie zastępuje pomiaru przy ścianie z książką między nogami.
    """
    return round(clamp_number(float(height_mm) * 0.465, 600.0, 1100.0, 810.0))


def sync_estimated_inseam() -> None:
    """Aktualizuje przekrok w callbacku przed ponownym utworzeniem widżetów."""
    if bool(st.session_state.get("auto_inseam", False)):
        st.session_state.inseam = estimate_inseam_from_height(
            float(st.session_state.get("height", 1750.0))
        )


def profile_login_gate() -> None:
    """Prosty ekran wejścia. Każda karta/przeglądarka ma własną sesję użytkownika."""
    if bool(st.session_state.user_logged_in):
        return

    left, center, right = st.columns([1, 1.4, 1])
    with center:
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), width=120)
        st.markdown("## BikeFit Studio Online")
        st.write("Wpisz imię lub pseudonim, aby rozpocząć własną konfigurację.")
        alias = st.text_input("Imię lub pseudonim", key="login_alias", max_chars=40)
        if st.button("Wejdź do konfiguratora", type="primary", use_container_width=True):
            clean_alias = alias.strip()
            if len(clean_alias) < 2:
                st.error("Wpisz imię lub pseudonim składający się z co najmniej 2 znaków.")
            else:
                st.session_state.user_alias = clean_alias
                st.session_state.user_logged_in = True
                st.session_state.profile_name = clean_alias
                st.rerun()
        st.caption("Każda osoba korzystająca z linku otrzymuje niezależną sesję w swojej przeglądarce.")
    st.stop()


def current_settings() -> FitSettings:
    """Zwraca ustawienia bez modyfikowania aktywnych widżetów Streamlit."""
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
    """Łączy bazę wbudowaną, wspólną bazę online i geometrię z sesji."""
    records: list[BikeGeometry] = list(load_bikes())
    index_by_name = {bike.name.casefold(): idx for idx, bike in enumerate(records)}

    shared_payloads, persistent, status = load_shared_geometry_payloads()
    st.session_state.shared_store_status = status
    st.session_state.shared_store_persistent = persistent

    for payload in [*shared_payloads, *st.session_state.custom_bikes]:
        try:
            bike = BikeGeometry.from_dict(dict(payload))
        except (TypeError, ValueError):
            continue
        key = bike.name.casefold()
        if key in index_by_name:
            records[index_by_name[key]] = bike
        else:
            index_by_name[key] = len(records)
            records.append(bike)
    return records


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
    # Oddzielny stan komponentów zapobiega konfliktom kluczy z ręczną edycją geometrii.
    st.session_state.component_stem_length = float(bike.stem_length)
    st.session_state.component_stem_angle = float(bike.stem_angle)
    st.session_state.component_hood_reach = float(bike.hood_reach)
    st.session_state.component_crank_length = float(bike.crank_length)


def apply_component_preset(stem_length: float | None = None, stem_angle: float | None = None,
                           crank_length: float | None = None, hood_reach: float | None = None,
                           bar_height_delta: float | None = None) -> None:
    """Bezpiecznie ustawia łatwo wymieniane komponenty przez callback Streamlit."""
    if stem_length is not None:
        st.session_state.component_stem_length = float(stem_length)
    if stem_angle is not None:
        st.session_state.component_stem_angle = float(stem_angle)
    if crank_length is not None:
        st.session_state.component_crank_length = float(crank_length)
    if hood_reach is not None:
        st.session_state.component_hood_reach = float(hood_reach)
    if bar_height_delta is not None:
        st.session_state.handlebar_stack_delta = float(bar_height_delta)


def reset_replaceable_components(base_bike: BikeGeometry) -> None:
    st.session_state.component_stem_length = float(base_bike.stem_length)
    st.session_state.component_stem_angle = float(base_bike.stem_angle)
    st.session_state.component_crank_length = float(base_bike.crank_length)
    st.session_state.component_hood_reach = float(base_bike.hood_reach)
    st.session_state.handlebar_stack_delta = 0.0
    st.session_state.handlebar_reach_delta = 0.0


def geometry_from_state(fallback: BikeGeometry) -> BikeGeometry:
    payload = fallback.to_dict()
    payload["name"] = str(st.session_state.get("geo_name", fallback.name))
    payload["bike_type"] = str(st.session_state.get("geo_type", fallback.bike_type))
    for field in payload:
        key = f"geo_{field}"
        if key in st.session_state and field not in ("name", "bike_type"):
            payload[field] = float(st.session_state[key])

    # Komponenty łatwe do wymiany są nakładane tylko na bieżącą symulację.
    # Mają własne klucze, więc nie kolidują z polami ręcznej edycji geometrii.
    component_map = {
        "stem_length": "component_stem_length",
        "stem_angle": "component_stem_angle",
        "hood_reach": "component_hood_reach",
        "crank_length": "component_crank_length",
    }
    for field, state_key in component_map.items():
        if state_key in st.session_state:
            payload[field] = float(st.session_state[state_key])
    return BikeGeometry.from_dict(payload)


SETTINGS_KEYS = (
    "saddle_height", "saddle_fore_aft", "handlebar_stack_delta",
    "handlebar_reach_delta", "cadence", "foot_angle", "style",
    "gear_weight", "tire_setup", "tire_surface", "tire_casing",
    "pressure_goal", "front_load_percent",
)


def apply_fit_result(settings: FitSettings, notes: list[str], status: str) -> None:
    """Stosuje bezpieczny wynik przed utworzeniem suwaków w bieżącym przebiegu."""
    settings = sanitize_fit_settings(settings)
    for key in SETTINGS_KEYS:
        # Lista stylu jest już utworzona wyżej w panelu; wartość pozostaje zgodna
        # z wybranym profilem, więc nie modyfikujemy aktywnego widżetu.
        if key == "style":
            continue
        st.session_state[key] = getattr(settings, key)
    st.session_state.fit_notes = list(notes)
    # Zatrzymujemy animację, aby pełne przeliczenie nie ścigało się z fragmentem SVG.
    st.session_state.animate_crank = False
    st.session_state.animation_last_ts = None
    st.session_state.animation_phase = float(st.session_state.get("phase", 270.0))
    st.session_state.fit_action_status = status
    st.session_state.fit_action_error = False

def run_base_fit_action(rider: Rider, bike: BikeGeometry) -> None:
    """Callback wykonywany przed renderowaniem widżetów w kolejnym przebiegu."""
    try:
        rec = recommend_and_evaluate(
            rider,
            bike,
            str(st.session_state.style),
            str(st.session_state.flexibility),
        )
        apply_fit_result(
            rec.settings,
            rec.notes,
            "Dobrano ustawienie bazowe. Sprawdź wartości M1–M4 i wprowadzaj zmiany stopniowo.",
        )
    except Exception as exc:
        st.session_state.fit_action_status = f"Nie udało się dobrać ustawienia: {exc}"
        st.session_state.fit_action_error = True


def run_optimize_fit_action(rider: Rider, bike: BikeGeometry) -> None:
    """Optymalizuje ustawienie w callbacku, zanim Streamlit utworzy suwaki."""
    try:
        result, optimized_analysis = optimize_fit(bike, rider, current_settings())
        apply_fit_result(
            result,
            [f"Optymalizacja zakończona wynikiem {optimized_analysis.score:.1f}/100."],
            f"Optymalizacja zakończona: {optimized_analysis.score:.1f}/100.",
        )
    except Exception as exc:
        st.session_state.fit_action_status = f"Nie udało się zoptymalizować ustawienia: {exc}"
        st.session_state.fit_action_error = True


def apply_pending_profile_payload() -> None:
    payload = st.session_state.get("pending_profile_payload")
    if not payload:
        return
    imported_bike = BikeGeometry.from_dict(payload.get("bike", {}))
    imported_rider = Rider.from_dict(payload.get("rider", {}))
    imported_settings = FitSettings.from_dict(payload.get("settings", {}))

    st.session_state.custom_bikes = [
        item for item in st.session_state.custom_bikes
        if item.get("name") != imported_bike.name
    ] + [imported_bike.to_dict()]
    st.session_state.selected_bike = imported_bike.name
    st.session_state.geometry_for = None
    st.session_state.profile_name = imported_rider.name
    st.session_state.height = float(imported_rider.height)
    st.session_state.inseam = float(imported_rider.inseam)
    st.session_state.weight = float(imported_rider.weight)
    st.session_state.flexibility = str(imported_rider.flexibility)
    for key in SETTINGS_KEYS:
        st.session_state[key] = getattr(imported_settings, key)
    st.session_state.animate_crank = False
    st.session_state.animation_last_ts = None
    st.session_state.pending_profile_payload = None
    st.session_state.fit_action_status = "Wczytano profil z pliku JSON."
    st.session_state.fit_action_error = False


def start_crank_animation() -> None:
    st.session_state.animate_crank = True
    st.session_state.animation_phase = float(st.session_state.get("phase", 270.0))
    st.session_state.animation_last_ts = None


def pause_crank_animation() -> None:
    st.session_state.animate_crank = False
    st.session_state.phase = float(st.session_state.get("animation_phase", st.session_state.get("phase", 270.0)))
    st.session_state.animation_last_ts = None


def reset_crank_animation() -> None:
    st.session_state.animate_crank = False
    st.session_state.phase = 270.0
    st.session_state.animation_phase = 270.0
    st.session_state.animation_last_ts = None


def display_phase_deg() -> float:
    return float(st.session_state.get("phase", 270.0))


def set_suggested_front_load(bike_type: str, style: str) -> None:
    st.session_state.front_load_percent = clamp_number(
        suggested_front_load_percent(bike_type, style), 35.0, 50.0, 44.0
    )


def render_smooth_animation(
    bike: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
    start_phase: float,
    show_measurements: bool,
    display_scale_percent: float,
    show_angles: bool,
) -> None:
    """Płynna animacja SVG sterowana kontrolkami umieszczonymi pod rysunkiem."""
    frame_count = 96
    # Malejący kąt daje ruch zgodny z ruchem wskazówek zegara w widoku z prawej strony.
    phases = [((start_phase - i * 360.0 / frame_count) % 360.0) for i in range(frame_count)]
    frames = [
        render_bike_svg(
            bike, rider, settings, phase, show_measurements, display_scale_percent, show_angles
        )
        for phase in phases
    ]
    rpm_value = int(round(float(settings.cadence)))
    speed_multiplier = max(0.1, float(st.session_state.get("animation_speed", 1.0)))
    html_doc = f"""
    <!doctype html><html><head><meta charset='utf-8'>
    <style>
      html,body{{margin:0;padding:0;background:#07131e;overflow:hidden;font-family:Segoe UI,Arial;color:#eef7ff}}
      #stage{{position:relative;width:100%;height:610px;background:#07131e;border-radius:16px;overflow:hidden}}
      .frame{{position:absolute;inset:0;display:none}}
      .frame.active{{display:block}}
      .frame svg{{display:block;width:100%;height:100%}}
      #badge{{position:absolute;right:18px;top:16px;z-index:10;background:rgba(7,19,30,.92);border:1px solid #4a718d;border-radius:12px;padding:9px 13px;color:#fff;font-weight:800;box-shadow:0 5px 18px rgba(0,0,0,.25)}}
      #badge span{{color:#67e4b5}}
    </style>
    </head><body>
      <div id='stage'><div id='badge'>Kadencja: <span>{rpm_value} rpm</span> &nbsp;•&nbsp; {speed_multiplier:.2f}×</div></div>
    <script>
      const svgFrames = {json.dumps(frames, ensure_ascii=False)};
      const stage = document.getElementById('stage');
      stage.insertAdjacentHTML('beforeend', svgFrames.map((svg,i)=>`<div class="frame ${{i===0?'active':''}}" data-i="${{i}}">${{svg}}</div>`).join(''));
      const nodes = Array.from(stage.querySelectorAll('.frame'));
      let currentIndex = 0;
      const durationMs = 60000 / Math.max(1, {rpm_value}) / {speed_multiplier:.3f};
      const startTime = performance.now();

      function showFrame(index) {{
        if (index === currentIndex && nodes[index].classList.contains('active')) return;
        nodes[currentIndex].classList.remove('active');
        currentIndex = index;
        nodes[currentIndex].classList.add('active');
      }}
      function tick(now) {{
        const progress = ((now - startTime) % durationMs) / durationMs;
        showFrame(Math.floor(progress * nodes.length) % nodes.length);
        requestAnimationFrame(tick);
      }}
      requestAnimationFrame(tick);
    </script></body></html>
    """
    components.html(html_doc, height=620, scrolling=False)


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


def saddle_shift_description(value_mm: float) -> tuple[str, str, str]:
    value = float(value_mm)
    if value > 0.5:
        return f"{abs(value):.0f} mm", "do przodu", f"+{abs(value):.0f} mm → PRZÓD"
    if value < -0.5:
        return f"{abs(value):.0f} mm", "do tyłu", f"{value:.0f} mm ← TYŁ"
    return "0 mm", "pozycja neutralna", "0 mm · POZYCJA NEUTRALNA"


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
    neutral_saddle = saddle_axis_top
    shift_value, shift_direction, shift_short = saddle_shift_description(settings.saddle_fore_aft)
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

        # Osobna regulacja siodła na szynach: pozycja neutralna osi sztycy -> rzeczywisty punkt S75.
        nx, ny = T(neutral_saddle)
        shift_color = "#b991ff"
        if abs(float(settings.saddle_fore_aft)) > 0.5:
            parts.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="none" stroke="{shift_color}" stroke-width="2"/>')
            parts.append(f'<line x1="{nx:.1f}" y1="{ny-20:.1f}" x2="{sx2:.1f}" y2="{sy2-20:.1f}" stroke="{shift_color}" stroke-width="3.4" marker-start="url(#arr)" marker-end="url(#arr)"/>')
            shift_label_x = (nx + sx2) / 2
            shift_label_y = min(ny, sy2) - 48
        else:
            shift_label_x = sx2
            shift_label_y = sy2 - 48
        parts.append(callout(shift_label_x, shift_label_y, "REGULACJA NA SZYNACH", shift_short, shift_color))

        m2y = min(sy2, hy) - 102
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



def render_interactive_measurements(bike: BikeGeometry, settings: FitSettings) -> None:
    """Interaktywny przyrząd pomiarowy działający całkowicie w przeglądarce."""
    bp = bike_points(bike, settings)
    ground_y = bike.bb_drop - bike.wheel_radius
    sta = math.radians(bike.seat_tube_angle)
    saddle_axis = (-settings.saddle_height * math.cos(sta), settings.saddle_height * math.sin(sta))
    saddle = bp["saddle"]
    saddle_nose = (saddle[0] + 78.0, saddle[1] - 2.0)
    saddle_rear = (saddle[0] - 82.0, saddle[1] + 2.0)
    hood = bp["hand"]
    pedal = (bike.crank_length, 0.0)
    rear_contact = (bp["rear_axle"][0], ground_y)
    front_contact = (bp["front_axle"][0], ground_y)
    top_mid = ((bp["seat_top"][0] + bp["head_top"][0]) / 2, (bp["seat_top"][1] + bp["head_top"][1]) / 2)
    raw_points = {
        "bb": ("BB — środek suportu", (0.0, 0.0), "Środek osi korby / suportu"),
        "s75": ("S75 — punkt siodła 75 mm", saddle, "Środek siodła w przekroju o szerokości 75 mm"),
        "saddle_axis": ("Oś siodła", saddle_axis, "Punkt na osi sztycy przy wysokości siodła"),
        "nose": ("Czubek siodła", saddle_nose, "Najbardziej wysunięty punkt nosa siodła"),
        "rear_saddle": ("Tył siodła", saddle_rear, "Najbardziej cofnięty punkt siodła"),
        "seat_top": ("Góra rury podsiodłowej", bp["seat_top"], "Środek górnej krawędzi rury podsiodłowej"),
        "head_top": ("Góra główki ramy", bp["head_top"], "Środek górnego łożyska sterów"),
        "head_bottom": ("Dół główki ramy", bp["head_bottom"], "Środek dolnego łożyska sterów"),
        "stem_end": ("Koniec mostka", bp["stem_end"], "Oś obejmy kierownicy"),
        "hood": ("Chwyt / klamkomanetka", hood, "Miejsce podparcia dłoni"),
        "rear_axle": ("Oś tylnego koła", bp["rear_axle"], "Środek osi tylnej piasty"),
        "front_axle": ("Oś przedniego koła", bp["front_axle"], "Środek osi przedniej piasty"),
        "rear_ground": ("Styk tylnego koła z podłożem", rear_contact, "Punkt styku opony z podłożem"),
        "front_ground": ("Styk przedniego koła z podłożem", front_contact, "Punkt styku opony z podłożem"),
        "pedal": ("Oś pedału", pedal, "Środek osi pedału przy korbie ustawionej poziomo"),
        "top_mid": ("Środek górnej rury", top_mid, "Połowa odcinka pomiędzy rurą podsiodłową i główką"),
    }
    xs = [v[1][0] for v in raw_points.values()] + [bp["rear_axle"][0]-bike.wheel_radius, bp["front_axle"][0]+bike.wheel_radius]
    ys = [v[1][1] for v in raw_points.values()] + [ground_y-50, bike.bb_drop+bike.wheel_radius]
    min_x, max_x = min(xs)-130, max(xs)+130
    min_y, max_y = min(ys)-80, max(ys)+120
    W, H = 1100, 590
    scale = min((W-100)/(max_x-min_x), (H-90)/(max_y-min_y))
    ox=(W-(max_x-min_x)*scale)/2
    oy=(H-(max_y-min_y)*scale)/2
    def T(pt):
        return (ox+(pt[0]-min_x)*scale, H-oy-(pt[1]-min_y)*scale)
    point_payload=[]
    for key,(name,pt,desc) in raw_points.items():
        x,y=T(pt)
        point_payload.append({"id":key,"name":name,"x":round(x,2),"y":round(y,2),"mx":round(pt[0],2),"my":round(pt[1],2),"desc":desc})
    def svg_line(a,b,color,width=5):
        x1,y1=T(a);x2,y2=T(b)
        return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'
    colors=palette(bike.bike_type)
    frame=[]
    for a,b in ((bp["rear_axle"],(0,0)),(bp["rear_axle"],bp["seat_top"]),((0,0),bp["seat_top"]),(bp["seat_top"],bp["head_top"]),((0,0),bp["head_bottom"]),(bp["head_bottom"],bp["head_top"]),(bp["head_bottom"],bp["front_axle"])):
        frame.append(svg_line(a,b,colors["dark"],10));frame.append(svg_line(a,b,colors["frame"],6))
    frame.append(svg_line(bp["seat_top"],saddle,"#d8e4ee",5))
    frame.append(svg_line(bp["head_top"],bp["stem_end"],"#e2ebf3",5))
    frame.append(svg_line(bp["stem_end"],hood,"#e2ebf3",5))
    sx,sy=T(saddle)
    frame.append(f'<line x1="{sx-38:.1f}" y1="{sy:.1f}" x2="{sx+42:.1f}" y2="{sy-2:.1f}" stroke="#edf3f8" stroke-width="11" stroke-linecap="round"/>')
    wheels=[]
    for c in (bp["rear_axle"],bp["front_axle"]):
        cx,cy=T(c);r=bike.wheel_radius*scale
        wheels.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#303941" stroke-width="10"/>')
        wheels.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r-8:.1f}" fill="none" stroke="#cfdae4" stroke-width="3"/>')
        wheels.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="#e4ebf2"/>')
    gx1,gy=T((min_x,ground_y));gx2,_=T((max_x,ground_y))
    payload=json.dumps(point_payload,ensure_ascii=False)
    presets=[
        ("Wysokość siodła", "bb", "saddle_axis", "direct", "Przyłóż początek metrówki do środka suportu i prowadź ją wzdłuż osi rury podsiodłowej oraz sztycy."),
        ("Setback S75", "bb", "s75", "horizontal", "Ustaw rower pionowo. Opuść pion z punktu S75 i zmierz poziomą odległość do pionu przechodzącego przez środek suportu."),
        ("S75 → chwyt", "s75", "hood", "direct", "Zmierz prostą odległość od punktu S75 do miejsca podparcia dłoni na klamkomanetce."),
        ("Drop siodło–chwyt", "s75", "hood", "vertical", "Zmierz różnicę wysokości punktu S75 i chwytu. Najłatwiej użyć poziomicy oraz metrówki."),
        ("Reach siodło–chwyt", "s75", "hood", "horizontal", "Zmierz poziomo od pionu przechodzącego przez S75 do pionu przechodzącego przez chwyt."),
        ("Długość mostka", "head_top", "stem_end", "direct", "Zmierz od środka górnej śruby sterów do osi obejmy kierownicy."),
        ("Rozstaw osi", "rear_axle", "front_axle", "horizontal", "Zmierz między środkami osi obu kół, równolegle do podłoża."),
        ("Długość korby", "bb", "pedal", "direct", "Zmierz od środka suportu do środka osi pedału."),
        ("BB drop", "bb", "rear_axle", "vertical", "Zmierz pionową różnicę pomiędzy osią piasty a osią suportu."),
        ("Front-center", "bb", "front_axle", "direct", "Zmierz od środka suportu do środka osi przedniego koła."),
    ]
    preset_json=json.dumps([{"name":a,"a":b,"b":c,"mode":d,"help":e} for a,b,c,d,e in presets],ensure_ascii=False)
    doc=f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box}} body{{margin:0;background:#07131e;color:#eef7ff;font-family:Segoe UI,Arial,sans-serif}}
    .wrap{{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px;height:780px}}
    .canvas{{position:relative;background:radial-gradient(circle at 50% 45%,#17354d,#07131e 65%);border:1px solid #35536b;border-radius:18px;overflow:hidden}}
    svg{{width:100%;height:100%;display:block}} .p{{cursor:pointer;transition:.15s}} .p:hover circle{{r:10;fill:#fff}} .p.sel circle{{fill:#ffcf67;stroke:#fff;stroke-width:3}}
    .panel{{background:#0e1e2c;border:1px solid #35536b;border-radius:18px;padding:14px;overflow:auto}}
    h3{{margin:0 0 8px}} .muted{{color:#9fb5c7;font-size:13px}} select,button{{width:100%;background:#173047;color:#fff;border:1px solid #4c708d;border-radius:9px;padding:9px;margin:4px 0;font-weight:650}}
    button:hover{{background:#24506d}} .preset{{text-align:left;font-size:13px}} .result{{background:#13283a;border:1px solid #4a6f8b;border-radius:13px;padding:12px;margin:10px 0}}
    .big{{font-size:25px;font-weight:850;color:#67e4b5}} .row{{display:grid;grid-template-columns:1fr 1fr;gap:7px}} .tip{{background:#1b2f40;border-left:4px solid #ffd166;padding:10px;border-radius:8px;font-size:13px;line-height:1.4}}
    .legend{{position:absolute;left:14px;top:12px;background:#0d1e2ddd;border:1px solid #3e607a;padding:8px 10px;border-radius:10px;font-size:12px}}
    @media(max-width:850px){{.wrap{{grid-template-columns:1fr;height:auto}}.canvas{{height:540px}}.panel{{max-height:none}}}}
    </style></head><body><div class="wrap"><div class="canvas"><div class="legend">Kliknij dwa charakterystyczne punkty. Punkty przyciągają pomiar automatycznie.</div>
    <svg id="s" viewBox="0 0 {W} {H}"><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="4.5" refY="4.5" orient="auto"><path d="M9 0 L0 4.5 L9 9" fill="none" stroke="#ffd166" stroke-width="1.5"/></marker></defs>
    <rect width="{W}" height="{H}" fill="transparent"/><line x1="{gx1:.1f}" y1="{gy:.1f}" x2="{gx2:.1f}" y2="{gy:.1f}" stroke="#607386" stroke-width="3"/>{''.join(wheels)}{''.join(frame)}<g id="measure"></g><g id="points"></g></svg></div>
    <div class="panel"><h3>📏 Interaktywne pomiary</h3><div class="muted">Wybierz gotowy pomiar albo kliknij dwa punkty na rowerze.</div>
    <label>Rodzaj wyniku</label><select id="mode"><option value="direct">Odległość prosta</option><option value="horizontal">Odległość pozioma</option><option value="vertical">Różnica wysokości</option><option value="all">Wszystkie składowe</option></select>
    <div class="row"><button id="clear">Wyczyść</button><button id="swap">Zamień punkty</button></div>
    <div class="result"><div id="names">Wybierz pierwszy punkt</div><div class="big" id="main">—</div><div id="details" class="muted"></div></div><div class="tip" id="tip">Kliknij punkt początkowy, a następnie końcowy.</div>
    <h3 style="margin-top:14px">Gotowe pomiary</h3><div id="presets"></div></div></div>
    <script>
    const points={payload}; const presets={preset_json}; let selected=[]; let help='';
    const pg=document.getElementById('points'), mg=document.getElementById('measure'), mode=document.getElementById('mode');
    const byId=id=>points.find(p=>p.id===id);
    points.forEach(p=>{{const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','p');g.dataset.id=p.id;g.innerHTML=`<circle cx="${{p.x}}" cy="${{p.y}}" r="7" fill="#67e4b5" stroke="#07131e" stroke-width="2"/><text x="${{p.x+10}}" y="${{p.y-10}}" fill="#f5fbff" font-size="11" font-weight="700">${{p.name.split(' — ')[0]}}</text>`;g.onclick=()=>pick(p.id);pg.appendChild(g)}});
    function pick(id){{if(selected.length>=2)selected=[];selected.push(id);help='';draw();}}
    function setSel(a,b,m,h){{selected=[a,b];mode.value=m;help=h;draw()}}
    function draw(){{document.querySelectorAll('.p').forEach(g=>g.classList.toggle('sel',selected.includes(g.dataset.id)));mg.innerHTML='';
      if(selected.length<2){{document.getElementById('names').textContent=selected.length?byId(selected[0]).name+' → wybierz drugi punkt':'Wybierz pierwszy punkt';document.getElementById('main').textContent='—';document.getElementById('details').textContent='';document.getElementById('tip').textContent=selected.length?byId(selected[0]).desc:'Kliknij punkt początkowy, a następnie końcowy.';return}}
      const a=byId(selected[0]),b=byId(selected[1]);const dx=b.mx-a.mx,dy=b.my-a.my,d=Math.hypot(dx,dy),ang=Math.atan2(dy,dx)*180/Math.PI;let value=d,label='Odległość prosta';if(mode.value==='horizontal'){{value=Math.abs(dx);label='Odległość pozioma'}}if(mode.value==='vertical'){{value=Math.abs(dy);label='Różnica wysokości'}}
      document.getElementById('names').textContent=a.name+' → '+b.name;document.getElementById('main').textContent=Math.round(value)+' mm';document.getElementById('details').textContent=`prosta: ${{Math.round(d)}} mm · pozioma: ${{Math.round(Math.abs(dx))}} mm · pionowa: ${{Math.round(Math.abs(dy))}} mm · kąt: ${{ang.toFixed(1)}}°`;
      document.getElementById('tip').textContent=help||`Punkt 1: ${{a.desc}}. Punkt 2: ${{b.desc}}. Wynik: ${{label.toLowerCase()}}.`;
      let x1=a.x,y1=a.y,x2=b.x,y2=b.y;if(mode.value==='horizontal')y2=y1;if(mode.value==='vertical')x2=x1;
      mg.innerHTML=`<line x1="${{x1}}" y1="${{y1}}" x2="${{x2}}" y2="${{y2}}" stroke="#ffd166" stroke-width="4" marker-start="url(#arrow)" marker-end="url(#arrow)"/><rect x="${{(x1+x2)/2-55}}" y="${{(y1+y2)/2-25}}" width="110" height="31" rx="9" fill="#0d1e2d" stroke="#ffd166"/><text x="${{(x1+x2)/2}}" y="${{(y1+y2)/2-5}}" fill="#fff" text-anchor="middle" font-size="14" font-weight="800">${{Math.round(value)}} mm</text>`;
    }}
    mode.onchange=draw;document.getElementById('clear').onclick=()=>{{selected=[];help='';draw()}};document.getElementById('swap').onclick=()=>{{selected.reverse();draw()}};
    const pr=document.getElementById('presets');presets.forEach(p=>{{const b=document.createElement('button');b.className='preset';b.textContent=p.name;b.onclick=()=>setSel(p.a,p.b,p.mode,p.help);pr.appendChild(b)}});draw();
    </script></body></html>'''
    components.html(doc, height=800, scrolling=False)


def measurement_values(bike: BikeGeometry, settings: FitSettings) -> list[tuple[str, str, str, str]]:
    bp = bike_points(bike, settings)
    setback = max(0.0, -bp["saddle"][0])
    drop = bp["saddle"][1] - bp["hand"][1]
    reach = bp["hand"][0] - bp["saddle"][0]
    shift_value, shift_direction, _ = saddle_shift_description(settings.saddle_fore_aft)
    return [
        ("M1", "Wysokość po osi rury i sztycy", f"{settings.saddle_height:.0f} mm", "#ffd166"),
        ("REG", "Przesunięcie siodła na szynach względem pozycji neutralnej", f"{shift_value} {shift_direction}", "#b991ff"),
        ("M2", "Setback punktu S75 względem pionu BB", f"{setback:.0f} mm za BB", "#57d3ff"),
        ("M3", "Pionowy drop S75 → chwyt H", f"{drop:.0f} mm", "#ff83c6"),
        ("M4", "Poziomy reach S75 → chwyt H", f"{reach:.0f} mm", "#8dea7b"),
        ("M5", "Długość korby BB → oś pedału", f"{bike.crank_length:.1f} mm", "#ff9f5a"),
    ]


def cycle_angle_records(bike: BikeGeometry, rider: Rider, settings: FitSettings) -> list[dict[str, float | str]]:
    records: list[dict[str, float | str]] = []
    for crank_angle in range(0, 361, 5):
        pose = calculate_pose(bike, rider, settings, float(crank_angle % 360))
        if pose.knee_flexion is not None:
            records.append({"Korba [°]": crank_angle, "Kąt [°]": round(pose.knee_flexion, 2), "Staw": "Kolano"})
        if pose.hip_angle is not None:
            records.append({"Korba [°]": crank_angle, "Kąt [°]": round(pose.hip_angle, 2), "Staw": "Biodro"})
    return records


def render_angle_chart_svg(
    records: list[dict[str, float | str]],
    current_phase: float,
) -> str:
    """Rysuje kontrastowy wykres SVG niezależny od motywu Vega/Streamlit."""
    knee = sorted(
        [(float(r["Korba [°]"]), float(r["Kąt [°]"])) for r in records if r["Staw"] == "Kolano"],
        key=lambda item: item[0],
    )
    hip = sorted(
        [(float(r["Korba [°]"]), float(r["Kąt [°]"])) for r in records if r["Staw"] == "Biodro"],
        key=lambda item: item[0],
    )
    all_values = [value for _angle, value in knee + hip]
    if not all_values:
        return '<div class="info-card">Brak prawidłowych danych do narysowania wykresu.</div>'

    W, H = 1120, 430
    left, right, top, bottom = 72, 28, 34, 58
    plot_w, plot_h = W - left - right, H - top - bottom
    raw_min, raw_max = min(all_values), max(all_values)
    y_min = math.floor((raw_min - 5.0) / 10.0) * 10.0
    y_max = math.ceil((raw_max + 5.0) / 10.0) * 10.0
    if y_max <= y_min:
        y_max = y_min + 10.0

    def x_of(angle: float) -> float:
        return left + max(0.0, min(360.0, angle)) / 360.0 * plot_w

    def y_of(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_h

    def polyline(data: list[tuple[float, float]], color: str) -> str:
        points = " ".join(f"{x_of(a):.1f},{y_of(v):.1f}" for a, v in data)
        return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'

    parts = [
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Wykres kątów kolana i biodra">',
        f'<rect width="{W}" height="{H}" rx="18" fill="#0c1a27" stroke="#36536b"/>',
    ]
    for angle in range(0, 361, 30):
        x = x_of(float(angle))
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}" stroke="#294158" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{H-25}" fill="#d9e7f2" font-size="12" text-anchor="middle" font-family="Segoe UI,Arial">{angle}</text>')
    step_y = 10.0
    tick = y_min
    while tick <= y_max + 0.001:
        y = y_of(tick)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#294158" stroke-width="1"/>')
        parts.append(f'<text x="{left-12}" y="{y+4:.1f}" fill="#d9e7f2" font-size="12" text-anchor="end" font-family="Segoe UI,Arial">{tick:.0f}°</text>')
        tick += step_y

    parts.append(polyline(knee, "#67e4b5"))
    parts.append(polyline(hip, "#57d3ff"))
    marker_x = x_of(float(current_phase) % 360.0)
    parts.append(f'<line x1="{marker_x:.1f}" y1="{top}" x2="{marker_x:.1f}" y2="{top+plot_h}" stroke="#ffd166" stroke-width="2.5" stroke-dasharray="7 6"/>')
    parts.append(f'<text x="{marker_x:.1f}" y="{top-10}" fill="#ffd166" font-size="12" font-weight="700" text-anchor="middle" font-family="Segoe UI,Arial">korba {float(current_phase)%360:.0f}°</text>')

    parts += [
        f'<line x1="{W-208}" y1="28" x2="{W-176}" y2="28" stroke="#67e4b5" stroke-width="4"/>',
        f'<text x="{W-168}" y="33" fill="#eef7ff" font-size="13" font-family="Segoe UI,Arial">Kolano</text>',
        f'<line x1="{W-104}" y1="28" x2="{W-72}" y2="28" stroke="#57d3ff" stroke-width="4"/>',
        f'<text x="{W-64}" y="33" fill="#eef7ff" font-size="13" font-family="Segoe UI,Arial">Biodro</text>',
        f'<text x="{left+plot_w/2:.1f}" y="{H-5}" fill="#d9e7f2" font-size="13" text-anchor="middle" font-family="Segoe UI,Arial">Pozycja korby [°]</text>',
        f'<text x="18" y="{top+plot_h/2:.1f}" fill="#d9e7f2" font-size="13" text-anchor="middle" transform="rotate(-90 18 {top+plot_h/2:.1f})" font-family="Segoe UI,Arial">Kąt stawu [°]</text>',
        '</svg>',
    ]
    return "".join(parts)


def report_html(bike: BikeGeometry, rider: Rider, settings: FitSettings) -> str:
    analysis = analyze_cycle(bike, rider, settings, samples=72)
    pressure = calculate_tire_pressure(rider, bike, settings)
    diagnostics = explain_fit(bike, rider, settings, analysis, threshold=90.0)
    frame_size = assess_frame_size(bike, rider, settings)
    rows = "".join(f"<tr><td>{c}</td><td>{n}</td><td><b>{v}</b></td></tr>" for c,n,v,_ in measurement_values(bike,settings))
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in analysis.messages)
    diagnostic_rows = "".join(
        f"<li><b>{html.escape(item.title)}</b> — {html.escape(item.why)} "
        f"<i>Korekta: {html.escape(item.correction)}</i></li>"
        for item in diagnostics
    ) or "<li>Ocena powyżej 90/100 — brak ostrzeżeń modelu.</li>"
    return f"""<!doctype html><html lang='pl'><meta charset='utf-8'><title>Raport BikeFit</title>
    <style>body{{font-family:Arial;max-width:900px;margin:30px auto;color:#10202e}}h1{{color:#244c68}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd8e0;padding:9px}}.brand{{color:#537089}}</style>
    <h1>BikeFit Studio Online v4.5</h1><div class='brand'>Autor: MisieK</div>
    <h2>{html.escape(bike.name)}</h2><p>Rowerzysta: {html.escape(rider.name)}, wzrost {rider.height:.0f} mm, przekrok {rider.inseam:.0f} mm, masa {rider.weight:.1f} kg.</p>
    <p><b>Ocena modelu: {analysis.score:.1f}/100</b></p>
    <table><tr><th>Kod</th><th>Pomiar</th><th>Wartość</th></tr>{rows}</table>
    <h3>Kąty</h3><p>Kolano: {analysis.knee_flexion_min:.1f}–{analysis.knee_flexion_max:.1f}°. Biodro: {analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°. Łokieć: {analysis.elbow_angle:.1f}°.</p>
    <h3>Ciśnienie startowe</h3><p>Przód {pressure.front_bar:.2f} bar / {pressure.front_psi:.0f} psi; tył {pressure.rear_bar:.2f} bar / {pressure.rear_psi:.0f} psi.</p>
    <h3>Ocena rozmiaru ramy</h3><p><b>{html.escape(frame_size.title)}</b></p><p>{html.escape(frame_size.summary)}</p>
    <ul>{''.join(f'<li>{html.escape(reason)}</li>' for reason in frame_size.reasons)}</ul>
    <p><b>Sugestia:</b> {html.escape(frame_size.suggestion)}</p>
    <h3>Wskazówki</h3><ul>{notes}</ul>
    <h3>Dlaczego ustawienie może być nieprawidłowe</h3><ul>{diagnostic_rows}</ul>
    <p><small>Wynik jest orientacyjny i nie zastępuje profesjonalnego bike fittingu ani konsultacji medycznej.</small></p></html>"""


init_state()
apply_pending_profile_payload()
sanitize_numeric_state()
profile_login_gate()

# Sidebar branding.
with st.sidebar:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=105)
    st.markdown("### BikeFit Studio Online")
    st.caption("Autor: **MisieK**")
    st.success(f"Profil: {st.session_state.user_alias}")
    st.markdown("---")

    catalog = bike_catalog()
    if st.session_state.shared_store_persistent:
        st.caption("☁️ " + st.session_state.shared_store_status)
    else:
        st.caption("💾 " + st.session_state.shared_store_status)
        st.markdown(
            '<div class="geometry-store-warning"><b>Baza lokalna nie jest trwała.</b><br>'
            'Geometrie zapisane tylko na serwerze mogą zniknąć po wdrożeniu nowej wersji. '
            'Pobierz kopię albo skonfiguruj ukrytą wspólną bazę online.</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "Pobierz kopię geometrii",
            data=geometry_backup_bytes(),
            file_name="bikefit_geometrie_backup.json",
            mime="application/json",
            key="sidebar_geometry_backup",
            use_container_width=True,
        )
    if st.session_state.geometry_action_status:
        if st.session_state.geometry_action_error:
            st.error(st.session_state.geometry_action_status)
        else:
            st.success(st.session_state.geometry_action_status)
        st.session_state.geometry_action_status = ""
        st.session_state.geometry_action_error = False

    if st.button("Odśwież wspólną bazę", key="refresh_shared_geometries", use_container_width=True):
        load_remote_shared_bikes_cached.clear()
        load_local_shared_bikes_cached.clear()
        st.rerun()
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

    built_in_names = {item.name.casefold() for item in load_bikes()}
    if current_name.casefold() not in built_in_names:
        with st.expander("🗑️ Usuń wybraną geometrię", expanded=False):
            st.warning(
                f"Usuniesz geometrię **{current_name}** ze wspólnej bazy. "
                "Ta operacja nie usuwa geometrii wbudowanych w program."
            )
            confirm_key = "confirm_delete_geometry"
            st.checkbox("Potwierdzam usunięcie tej geometrii", key=confirm_key)
            if st.button(
                "Usuń geometrię",
                key="delete_selected_geometry",
                use_container_width=True,
                disabled=not bool(st.session_state.get(confirm_key, False)),
            ):
                ok, message = delete_shared_geometry(current_name)
                st.session_state.geometry_action_status = message
                st.session_state.geometry_action_error = not ok
                if ok:
                    fallback_name = load_bikes()[0].name
                    st.session_state.selected_bike = fallback_name
                    st.session_state.geometry_for = ""
                st.rerun()

    with st.expander("🌐 Import geometrii z linku", expanded=False):
        st.caption("Otwórz katalog, wybierz dokładny model, rocznik i rozmiar, a następnie wklej adres strony. Po pobraniu możesz wpisać własną nazwę geometrii przed zapisaniem.")
        external_link_button("Otwórz Bike Insights", "https://bikeinsights.com/search")
        external_link_button("Otwórz Geometry Geeks", "https://geometrygeeks.bike/")
        external_link_button("Otwórz Bike-Stats", "https://www.bike-stats.de/en/")
        st.text_input(
            "Adres konkretnego modelu i rozmiaru",
            key="sidebar_import_url",
            placeholder="https://...",
            help="Wklej adres strony zawierającej tabelę geometrii konkretnego rozmiaru ramy.",
        )
        st.text_input(
            "Proponowana nazwa geometrii (opcjonalnie)",
            key="sidebar_import_custom_name",
            placeholder="np. KROSS Esker 7.0 2025 M",
            help="Możesz wpisać nazwę już teraz albo poprawić ją po pobraniu danych.",
            max_chars=120,
        )

        if st.button("Pobierz geometrię", key="import_geometry_sidebar", use_container_width=True, type="primary"):
            import_url = str(st.session_state.sidebar_import_url).strip()
            if not import_url:
                st.session_state.sidebar_import_status = "Wklej najpierw adres strony z geometrią."
                st.session_state.sidebar_import_notes = []
            else:
                try:
                    with st.spinner("Pobieram stronę i rozpoznaję geometrię…"):
                        imported, notes = safe_import_url(import_url, geometry_from_state(base_bike))
                    suggested_name = clean_geometry_name(
                        st.session_state.sidebar_import_custom_name, imported.name
                    )
                    st.session_state.pending_import_geometry = imported.to_dict()
                    st.session_state.pending_import_notes = list(notes)
                    st.session_state.sidebar_import_preview_name = suggested_name
                    st.session_state.sidebar_import_status = "Geometria pobrana. Sprawdź nazwę i zapisz ją poniżej."
                    st.session_state.sidebar_import_notes = []
                    st.rerun()
                except Exception as exc:
                    st.session_state.pending_import_geometry = None
                    st.session_state.pending_import_notes = []
                    st.session_state.sidebar_import_status = f"Import nie powiódł się: {exc}"
                    st.session_state.sidebar_import_notes = []

        pending_import = st.session_state.get("pending_import_geometry")
        if pending_import:
            st.markdown("##### Sprawdź przed zapisaniem")
            st.text_input(
                "Nazwa zapisywanej geometrii",
                key="sidebar_import_preview_name",
                max_chars=120,
                help="Ta nazwa pojawi się na liście rowerów u wszystkich użytkowników wspólnej bazy.",
            )
            preview_bike = imported_geometry_with_name(
                pending_import, st.session_state.sidebar_import_preview_name
            )
            st.caption(
                f"{preview_bike.bike_type} • Stack {preview_bike.stack:.0f} mm • "
                f"Reach {preview_bike.reach:.0f} mm • korba {preview_bike.crank_length:.1f} mm"
            )
            save_col, cancel_col = st.columns([2, 1])
            if save_col.button(
                "Zapisz i zastosuj",
                key="save_imported_geometry",
                use_container_width=True,
                type="primary",
            ):
                final_name = clean_geometry_name(
                    st.session_state.sidebar_import_preview_name, preview_bike.name
                )
                if not final_name.strip():
                    st.warning("Wpisz nazwę geometrii.")
                else:
                    imported = replace(preview_bike, name=final_name)
                    remember_geometry_in_session(imported)
                    _saved_globally, save_message = persist_shared_geometry(
                        imported, str(st.session_state.user_alias)
                    )
                    st.session_state.selected_bike = imported.name
                    reset_geometry_state(imported)
                    st.session_state.geometry_for = imported.name
                    st.session_state.sidebar_import_status = f"Zapisano: {imported.name}. {save_message}"
                    st.session_state.sidebar_import_notes = list(
                        st.session_state.get("pending_import_notes", [])
                    )
                    st.session_state.pending_import_geometry = None
                    st.session_state.pending_import_notes = []
                    st.rerun()
            if cancel_col.button(
                "Anuluj", key="cancel_imported_geometry", use_container_width=True
            ):
                st.session_state.pending_import_geometry = None
                st.session_state.pending_import_notes = []
                st.session_state.sidebar_import_status = "Anulowano zapis pobranej geometrii."
                st.rerun()

        if st.session_state.sidebar_import_status:
            if st.session_state.sidebar_import_status.startswith(("Zapisano", "Geometria pobrana")):
                st.success(st.session_state.sidebar_import_status)
            else:
                st.warning(st.session_state.sidebar_import_status)
        for import_note in st.session_state.sidebar_import_notes:
            st.caption(f"• {import_note}")

    with st.expander("📐 Ręczna edycja geometrii", expanded=False):
        st.caption("Zmiany działają od razu w symulacji. Po zapisaniu geometria pojawi się we wspólnej liście wyboru dla wszystkich użytkowników.")
        st.text_input("Nazwa geometrii", key="geo_name")
        st.selectbox("Typ roweru", ["Gravel", "Road", "MTB", "Trekking", "City", "TT"], key="geo_type")
        quick_cols = st.columns(2)
        for i, (label_text, field, step) in enumerate(GEOMETRY_FIELDS):
            quick_cols[i % 2].number_input(label_text, key=f"geo_{field}", step=step, format="%.1f")
        if st.button("Zapisz jako własną geometrię", key="save_geometry_sidebar", use_container_width=True, type="primary"):
            edited = geometry_from_state(base_bike)
            remember_geometry_in_session(edited)
            _saved_globally, save_message = persist_shared_geometry(
                edited, str(st.session_state.user_alias)
            )
            st.session_state.selected_bike = edited.name
            st.session_state.geometry_for = edited.name
            st.session_state.sidebar_import_status = save_message
            st.rerun()

    with st.expander("🔧 Komponenty łatwe do wymiany", expanded=True):
        st.caption(
            "Te ustawienia dotyczą części, które najczęściej zmienia się bez wymiany ramy. "
            "Wpływają od razu na symulację, kąty i ocenę pozycji, ale nie zmieniają wymiarów samej ramy."
        )

        comp_c1, comp_c2 = st.columns(2)
        comp_c1.number_input(
            "Długość korby [mm]", min_value=150.0, max_value=190.0,
            key="component_crank_length", step=2.5, format="%.1f",
            help="Najczęściej spotykane wartości: 165, 170, 172.5 i 175 mm."
        )
        comp_c2.number_input(
            "Długość mostka [mm]", min_value=40.0, max_value=150.0,
            key="component_stem_length", step=5.0, format="%.0f",
            help="Krótszy mostek skraca zasięg, dłuższy wydłuża kokpit."
        )

        comp_c3, comp_c4 = st.columns(2)
        comp_c3.number_input(
            "Kąt mostka [°]", min_value=-25.0, max_value=35.0,
            key="component_stem_angle", step=1.0, format="%.1f",
            help="Dodatni kąt podnosi kierownicę; ujemny zwykle ją obniża i wydłuża pozycję."
        )
        comp_c4.slider(
            "Wysokość podkładek pod mostkiem [mm]", -40.0, 80.0,
            key="handlebar_stack_delta", step=5.0,
            help=(
                "0 mm oznacza pozycję zapisaną w geometrii. Wartość dodatnia podnosi chwyt, "
                "ujemna symuluje usunięcie podkładek, odwrócenie mostka lub niższy kokpit."
            )
        )
        st.caption(
            "To jest regulacja wysokości mostka na rurze sterowej. Typowe realne zmiany podkładkami "
            "to około 5–30 mm; większe wartości traktuj jako symulację także kąta i konstrukcji mostka."
        )

        comp_c5, comp_c6 = st.columns(2)
        comp_c5.number_input(
            "Zasięg kierownicy / chwytu [mm]", min_value=35.0, max_value=130.0,
            key="component_hood_reach", step=2.5, format="%.1f",
            help="Dla baranka odpowiada głównie zasięgowi kierownicy i położeniu klamkomanetek; dla prostej kierownicy — położeniu środka chwytu."
        )
        comp_c6.slider(
            "Dodatkowa korekta zasięgu [mm]", -60.0, 60.0,
            key="handlebar_reach_delta", step=5.0,
            help="Szybka symulacja przesunięcia chwytu bez zmiany zapisanej geometrii ramy."
        )

        st.markdown("**Szybkie ustawienia kokpitu**")
        cockpit_preset = st.selectbox(
            "Wybierz charakter kokpitu",
            ["Komfort — krócej i wyżej", "Neutralnie", "Sportowo — dłużej i niżej"],
            key="component_cockpit_preset",
            label_visibility="collapsed",
        )
        preset_map = {
            "Komfort — krócej i wyżej": {"stem_length": 70.0, "stem_angle": 10.0, "bar_height_delta": 25.0},
            "Neutralnie": {"stem_length": 90.0, "stem_angle": 0.0, "bar_height_delta": 0.0},
            "Sportowo — dłużej i niżej": {"stem_length": 110.0, "stem_angle": -7.0, "bar_height_delta": -15.0},
        }
        st.button(
            "Zastosuj ustawienie kokpitu",
            key="apply_component_cockpit_preset",
            use_container_width=True,
            on_click=apply_component_preset,
            kwargs=preset_map[cockpit_preset],
        )

        st.markdown("**Szybki wybór korby**")
        crank_preset = st.selectbox(
            "Długość korby",
            [165.0, 170.0, 172.5, 175.0],
            key="component_crank_preset_select",
            format_func=lambda value: f"{value:g} mm",
            label_visibility="collapsed",
        )
        st.button(
            f"Ustaw korbę {crank_preset:g} mm",
            key="apply_component_crank_preset",
            use_container_width=True,
            on_click=apply_component_preset,
            kwargs={"crank_length": crank_preset},
        )

        st.button(
            "↺ Przywróć komponenty z geometrii", key="reset_replaceable_components",
            use_container_width=True, on_click=reset_replaceable_components, args=(base_bike,)
        )
        with st.expander("ℹ️ Jak interpretować zmiany", expanded=False):
            st.caption(
                "Zmiana długości korby może wymagać ponownego ustawienia wysokości siodła. "
                "Po zmianie mostka lub podkładek obserwuj ocenę zasięgu, pochylenie tułowia, "
                "kąt łokcia i rozkład nacisku na dłonie."
            )

    bike = geometry_from_state(base_bike)

    st.markdown("#### Rowerzysta")
    st.text_input("Nazwa profilu", key="profile_name")

    # Opcja jest renderowana przed polem przekroku. Dzięki temu wartość
    # orientacyjna trafia do session_state zanim Streamlit utworzy widżet.
    auto_inseam_enabled = st.checkbox(
        "Nie znam przekroku — oblicz orientacyjnie z wzrostu",
        key="auto_inseam",
        on_change=sync_estimated_inseam,
    )

    c1, c2 = st.columns(2)
    c1.number_input(
        "Wzrost [mm]",
        1400.0,
        2200.0,
        key="height",
        step=1.0,
        on_change=sync_estimated_inseam,
    )

    if auto_inseam_enabled:
        calculated_inseam = estimate_inseam_from_height(float(st.session_state.height))
        # Pole jeszcze nie zostało utworzone w tym przebiegu, więc ustawienie
        # wartości jest bezpieczne i od razu widoczne w interfejsie.
        st.session_state.inseam = float(calculated_inseam)

    c2.number_input(
        "Przekrok [mm]",
        600.0,
        1100.0,
        key="inseam",
        step=1.0,
        format="%.0f",
        disabled=auto_inseam_enabled,
        help="Najdokładniej zmierzyć od podłogi do krocza przy ścianie. Możesz też użyć wartości orientacyjnej z wzrostu.",
    )

    if auto_inseam_enabled:
        st.caption(
            f"Wpisano automatycznie **{float(st.session_state.inseam):.0f} mm** "
            f"(około 46,5% wzrostu). Wartość jest aktualizowana po każdej zmianie wzrostu."
        )
    c3, c4 = st.columns(2)
    c3.number_input("Masa [kg]", 35.0, 220.0, key="weight", step=0.5)
    c4.selectbox("Mobilność", ["Ograniczona", "Średnia", "Dobra"], key="flexibility")
    st.selectbox("Charakter pozycji", ["Komfortowa", "Zrównoważona", "Sportowa"], key="style")

    rider = current_rider()

    if st.button("Zmień użytkownika", key="logout_profile", use_container_width=True):
        for session_key in list(st.session_state.keys()):
            del st.session_state[session_key]
        st.rerun()

    st.button(
        "Dobierz ustawienie bazowe",
        key="base_fit_button",
        use_container_width=True,
        type="primary",
        on_click=run_base_fit_action,
        args=(rider, bike),
    )

    st.button(
        "Optymalizuj aktualne ustawienie",
        key="optimize_fit_button",
        use_container_width=True,
        on_click=run_optimize_fit_action,
        args=(rider, bike),
    )

    # Callback uruchamia się przed ponownym renderowaniem, dlatego suwaki poniżej
    # otrzymują już nowe wartości i nie dochodzi do modyfikacji aktywnego widżetu.

    if st.session_state.fit_action_status:
        if st.session_state.fit_action_error:
            st.error(st.session_state.fit_action_status)
        else:
            st.success(st.session_state.fit_action_status)

    st.markdown("#### Regulacja")
    st.slider("M1 wysokość siodła [mm]", 500.0, 900.0, key="saddle_height", step=1.0)
    st.slider("Przesunięcie siodła na szynach [mm] (+ przód / − tył)", -60.0, 80.0, key="saddle_fore_aft", step=1.0)
    _shift_value, _shift_direction, _ = saddle_shift_description(float(st.session_state.saddle_fore_aft))
    st.info(f"Ustaw siodło: **{_shift_value} {_shift_direction}** względem pozycji neutralnej na szynach.")
    st.caption("Długość korby, mostek, jego kąt, **podkładki pod mostkiem** oraz zasięg kierownicy ustawisz wyżej w rozwiniętym panelu **🔧 Komponenty łatwe do wymiany**.")
    st.slider("Kąt stopy [°]", -20.0, 15.0, key="foot_angle", step=1.0)
    st.caption("Sterowanie animacją, kadencją, skalą i oznaczeniami znajduje się pod rysunkiem roweru w zakładce **Symulacja**.")

settings = current_settings()
rider = current_rider()
analysis = analyze_cycle(bike, rider, settings, samples=72)
fit_diagnostics = explain_fit(bike, rider, settings, analysis, threshold=90.0)
frame_size_assessment = assess_frame_size(bike, rider, settings)
pressure = calculate_tire_pressure(rider, bike, settings)

st.markdown("""
<div class="hero">
  <h1>BikeFit Studio Online v4.5</h1>
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

st.markdown(render_fit_diagnostics(fit_diagnostics, analysis.score), unsafe_allow_html=True)
st.markdown(render_frame_size_assessment(frame_size_assessment, compact=True), unsafe_allow_html=True)
st.caption("Ocena rozmiaru ramy aktualizuje się automatycznie po każdej zmianie wzrostu, przekroku, stylu, geometrii lub ustawień kokpitu — nie trzeba ponownie uruchamiać optymalizacji.")

main_tab, config_tab, tire_tab, geometry_tab, import_tab, measurements_tab, guides_tab, angles_tab, report_tab = st.tabs([
    "Symulacja", "Wymiary i konfigurator", "Opony i ciśnienie", "Geometria roweru", "Import online", "📏 Pomiary roweru", "🧭 Jak mierzyć", "Wykresy kątów", "Raport",
])

with main_tab:
    if bool(st.session_state.animate_crank):
        render_smooth_animation(
            bike,
            rider,
            settings,
            float(st.session_state.phase),
            bool(st.session_state.show_measurements),
            float(st.session_state.simulation_scale),
            bool(st.session_state.show_angles),
        )
    else:
        st.markdown(
            render_bike_svg(
                bike,
                rider,
                settings,
                float(st.session_state.phase),
                bool(st.session_state.show_measurements),
                float(st.session_state.simulation_scale),
                bool(st.session_state.show_angles),
            ),
            unsafe_allow_html=True,
        )

    st.markdown("### Sterowanie symulacją")
    with st.container(border=True):
        top_left, top_right = st.columns(2)
        top_left.slider(
            "Kadencja [rpm]",
            40.0,
            130.0,
            key="cadence",
            step=1.0,
            help="Kadencja steruje tempem animacji oraz jest używana w aktualnym profilu ustawienia.",
        )
        top_right.slider(
            "Pozycja korby [°]",
            0.0,
            359.0,
            key="phase",
            step=1.0,
            disabled=bool(st.session_state.animate_crank),
        )

        play_col, pause_col, reset_col, state_col = st.columns([1, 1, 1, 2])
        play_col.button("▶ Play", key="anim_play", use_container_width=True, on_click=start_crank_animation)
        pause_col.button("⏸ Pauza", key="anim_pause", use_container_width=True, on_click=pause_crank_animation)
        reset_col.button("↺ Reset", key="anim_reset", use_container_width=True, on_click=reset_crank_animation)
        state_col.info(
            f"Stan: **{'odtwarzanie' if bool(st.session_state.animate_crank) else 'pauza'}** · "
            f"{float(st.session_state.cadence):.0f} rpm · "
            f"{float(st.session_state.animation_speed):.2f}×"
        )

        speed_col, scale_col = st.columns(2)
        speed_col.slider("Prędkość animacji [×]", 0.25, 2.0, key="animation_speed", step=0.25)
        scale_col.slider(
            "Skala symulacji [%]",
            65.0,
            100.0,
            key="simulation_scale",
            step=1.0,
            help="Zmniejsz, aby cały rower i rowerzysta mieścili się wygodniej na ekranie.",
        )

        option_col1, option_col2 = st.columns(2)
        option_col1.checkbox("Pokaż kąty na rysunku", key="show_angles")
        option_col2.checkbox("Pokaż wymiary M1–M5", key="show_measurements")
        st.caption("Animacja działa zgodnie z kadencją × ustawiony mnożnik prędkości.")

    cards = "".join(
        f'<div class="measure-card"><div class="measure-code" style="color:{color}">{code}</div><div class="measure-name">{name}</div><div class="measure-value">{value}</div></div>'
        for code, name, value, color in measurement_values(bike, settings)
    )
    st.markdown(f'<div class="measure-grid">{cards}</div>', unsafe_allow_html=True)

    _shift_value, _shift_direction, _ = saddle_shift_description(settings.saddle_fore_aft)
    _bp_for_shift = bike_points(bike, settings)
    _setback_for_shift = max(0.0, -_bp_for_shift["saddle"][0])
    st.success(
        f"**Wynik ustawienia siodła:** przesuń siodło **{_shift_value} {_shift_direction}** na szynach względem pozycji neutralnej. "
        f"Po ustawieniu punkt S75 powinien mieć około **{_setback_for_shift:.0f} mm setbacku za osią suportu (BB)**."
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.info(f"**Kolano:** {analysis.knee_flexion_min:.1f}–{analysis.knee_flexion_max:.1f}°")
    a2.info(f"**Biodro:** {analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°")
    a3.info(f"**Łokieć:** {analysis.elbow_angle:.1f}°")
    a4.info(f"**Tułów:** {analysis.torso_angle:.1f}°")

    st.info("S75 oznacza środek siodła w miejscu, w którym siodło ma 75 mm szerokości. Animacja działa płynnie w przeglądarce i obraca korbę zgodnie z ruchem wskazówek zegara w widoku z prawej strony roweru.")

with config_tab:
    setting_rows = [
        ("Wysokość siodła", f"{settings.saddle_height:.0f} mm"),
        ("Przesunięcie siodła na szynach", f"{saddle_shift_description(settings.saddle_fore_aft)[0]} {saddle_shift_description(settings.saddle_fore_aft)[1]}"),
        ("Kierownica — wysokość", f"{settings.handlebar_stack_delta:+.0f} mm"),
        ("Kierownica — zasięg", f"{settings.handlebar_reach_delta:+.0f} mm"),
        ("Pochylenie tułowia", f"{analysis.torso_angle:.1f}°"),
        ("Kąt łokcia", f"{analysis.elbow_angle:.1f}°"),
        ("Zakres biodra", f"{analysis.hip_angle_min:.1f}–{analysis.hip_angle_max:.1f}°"),
    ]
    rows_html = "".join(
        f'<div class="config-row"><span>{html.escape(name)}</span><b>{html.escape(value)}</b></div>'
        for name, value in setting_rows
    )
    model_notes = list(analysis.messages) + list(st.session_state.fit_notes)
    notes_html = "".join(
        f'<div class="config-note">• {html.escape(str(note))}</div>' for note in model_notes
    ) or '<div class="config-note">Brak dodatkowych uwag.</div>'
    guide_html = "".join(
        f'<div>• {html.escape(str(line))}</div>' for line in measurement_guide(bike, settings)
    )
    diagnostic_detail_html = render_fit_diagnostics(fit_diagnostics, analysis.score)
    config_html = f'''
        <div class="config-grid">
          <section class="config-card"><h3>Aktualne ustawienie</h3>{rows_html}</section>
          <section class="config-card"><h3>Wskazówki modelu</h3>{notes_html}
            <div class="config-warning">Wprowadzaj zmiany na prawdziwym rowerze stopniowo, zwykle po 2–5 mm, i testuj każdą zmianę podczas jazdy.</div>
          </section>
        </div>
        {render_frame_size_assessment(frame_size_assessment)}
        {diagnostic_detail_html}
        <section class="measure-help"><h3>Jak zmierzyć samą metrówką</h3>{guide_html}</section>
    '''
    st.markdown(config_html, unsafe_allow_html=True)

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
    st.button(
        "Ustaw sugerowany rozkład masy",
        on_click=set_suggested_front_load,
        args=(bike.bike_type, settings.style),
        use_container_width=True,
    )

with geometry_tab:
    st.subheader("Geometria aktywnego roweru")
    st.info("Import z linku i ręczna edycja geometrii znajdują się w panelu po lewej: **🌐 Import geometrii z linku** oraz **📐 Ręczna edycja geometrii**. Zmiany są widoczne w symulacji natychmiast.")
    active_geometry = geometry_from_state(base_bike)
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Stack", f"{active_geometry.stack:.1f} mm")
    g2.metric("Reach", f"{active_geometry.reach:.1f} mm")
    g3.metric("Kąt rury podsiodłowej", f"{active_geometry.seat_tube_angle:.1f}°")
    g4.metric("Rozstaw osi", f"{active_geometry.wheelbase:.1f} mm")

    st.markdown(render_frame_size_assessment(frame_size_assessment), unsafe_allow_html=True)

    st.markdown("#### Kopia i przywracanie własnych geometrii")
    backup_col, restore_col = st.columns(2)
    with backup_col:
        st.download_button(
            "Pobierz kopię wszystkich dodanych geometrii",
            data=geometry_backup_bytes(),
            file_name="bikefit_geometrie_backup.json",
            mime="application/json",
            key="geometry_backup_download",
            use_container_width=True,
        )
    with restore_col:
        geometry_backup_upload = st.file_uploader(
            "Przywróć kopię geometrii JSON",
            type=["json"],
            key="geometry_backup_upload",
            help="Wczytaj plik pobrany wcześniej z aplikacji. Rekordy o tej samej nazwie zostaną zaktualizowane.",
        )
    if geometry_backup_upload is not None and st.button(
        "Przywróć geometrie z kopii",
        key="restore_geometry_backup",
        use_container_width=True,
    ):
        try:
            restored_payloads = parse_store_document(geometry_backup_upload.getvalue())
            if not restored_payloads:
                st.warning("Plik nie zawiera żadnych geometrii.")
            else:
                saved_count = 0
                last_message = ""
                for payload in restored_payloads:
                    restored_bike = BikeGeometry.from_dict(payload)
                    remember_geometry_in_session(restored_bike)
                    _persistent_save, last_message = persist_shared_geometry(
                        restored_bike, str(st.session_state.user_alias)
                    )
                    saved_count += 1
                st.success(f"Przywrócono {saved_count} geometrii. {last_message}")
                st.rerun()
        except Exception as exc:
            st.error(f"Nie udało się przywrócić kopii: {exc}")

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
        external_link_button("Bike-Stats", "https://www.bike-stats.de/en/")
    url = st.text_input("Adres strony z geometrią", placeholder="https://...")
    if st.button("Pobierz i rozpoznaj geometrię", type="primary"):
        if not url:
            st.error("Wklej adres strony.")
        else:
            try:
                with st.spinner("Pobieram stronę i rozpoznaję parametry…"):
                    imported, notes = safe_import_url(url, bike)
                remember_geometry_in_session(imported)
                _saved_globally, save_message = persist_shared_geometry(
                    imported, str(st.session_state.user_alias)
                )
                st.session_state.selected_bike = imported.name
                reset_geometry_state(imported)
                st.session_state.geometry_for = imported.name
                st.success("Import zakończony. " + save_message)
                for note in notes:
                    st.write(f"• {note}")
            except Exception as exc:
                st.error(f"Import nie powiódł się: {exc}")
    st.caption("Niektóre strony blokują automatyczny odczyt. W takim przypadku przepisz wartości w zakładce geometrii.")


with measurements_tab:
    st.subheader("Interaktywne pomiary rzeczywistego roweru")
    st.write("Kliknij dwa charakterystyczne punkty albo wybierz gotowy pomiar. Aplikacja pokaże odległość prostą, poziomą, pionową i kąt oraz podpowie, jak wykonać pomiar zwykłą metrówką.")
    render_interactive_measurements(bike, settings)
    st.info("Rysunek jest modelem geometrycznym. Wartości służą do przeniesienia ustawienia na realny rower. Przy pomiarze ustaw rower pionowo na równym podłożu i zawsze używaj tych samych punktów referencyjnych.")

with guides_tab:
    st.subheader("Wizualne instrukcje pomiarowe")
    st.write("Wybierz element, aby zobaczyć dokładny punkt przyłożenia metrówki. Punkt chwytu automatycznie dopasowuje się do typu aktywnego roweru: baranek dla gravela/szosy albo grip dla MTB i kierownicy prostej.")
    components.html(build_visual_measurement_guides_html(bike.bike_type), height=590, scrolling=True)
    st.info("Ilustracje są własnymi grafikami technicznymi SVG programu — ostre na telefonie i komputerze, bez zależności od zewnętrznych zdjęć.")


with angles_tab:
    st.subheader("Wykresy kątów przez pełny obrót korby")
    angle_records = cycle_angle_records(bike, rider, settings)
    st.markdown(
        render_angle_chart_svg(angle_records, float(st.session_state.phase)),
        unsafe_allow_html=True,
    )
    knee_values = [float(r["Kąt [°]"]) for r in angle_records if r["Staw"] == "Kolano"]
    hip_values = [float(r["Kąt [°]"]) for r in angle_records if r["Staw"] == "Biodro"]
    c_knee, c_hip = st.columns(2)
    if knee_values:
        c_knee.metric("Kolano — zakres", f"{min(knee_values):.1f}–{max(knee_values):.1f}°")
    if hip_values:
        c_hip.metric("Biodro — zakres", f"{min(hip_values):.1f}–{max(hip_values):.1f}°")
    st.caption("Zielona linia pokazuje kąt kolana, niebieska otwarcie biodra, a żółta linia aktualną pozycję korby.")

with report_tab:
    st.subheader("Raport i kopia profilu")
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
            st.session_state.pending_profile_payload = {
                "bike": imported_bike.to_dict(),
                "rider": imported_rider.to_dict(),
                "settings": imported_settings.to_dict(),
            }
            st.rerun()
        except Exception as exc:
            st.error(f"Nie udało się wczytać profilu: {exc}")

render_visitor_counter()
st.markdown("""
<div class="footer-note">BikeFit Studio Online v4.5 • autor: MisieK • narzędzie orientacyjne, nie wyrób medyczny<br><span style="font-size:.72rem;color:#71899c">Licznik wizyt nie zapisuje danych profilu.</span></div>
""", unsafe_allow_html=True)
