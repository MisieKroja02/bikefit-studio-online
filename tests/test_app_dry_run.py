from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class FakeContext:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        return getattr(self.st, name)


class FakeCache:
    def __call__(self, func=None, **kwargs):
        def decorate(fn):
            fn.clear = lambda: None
            return fn
        if func is not None and callable(func):
            return decorate(func)
        return decorate


class FakeStreamlit(types.ModuleType):
    def __init__(self, clicked_keys=None):
        super().__init__("streamlit")
        self.clicked_keys = set(clicked_keys or [])
        self.session_state = SessionState(user_logged_in=True, user_alias="Tester")
        self.secrets = {}
        self.cache_data = FakeCache()
        self.sidebar = FakeContext(self)

    def set_page_config(self, **kwargs): pass
    def markdown(self, *args, **kwargs): pass
    def caption(self, *args, **kwargs): pass
    def write(self, *args, **kwargs): pass
    def image(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def success(self, *args, **kwargs): pass
    def subheader(self, *args, **kwargs): pass
    def metric(self, *args, **kwargs): pass
    def download_button(self, *args, **kwargs): return False
    def file_uploader(self, *args, **kwargs): return None
    def button(self, *args, **kwargs):
        key = kwargs.get("key")
        clicked = key in self.clicked_keys
        if clicked:
            self.clicked_keys.remove(key)
            callback = kwargs.get("on_click")
            if callback:
                callback(*kwargs.get("args", ()), **kwargs.get("kwargs", {}))
        return clicked
    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeContext(self) for _ in range(count)]
    def tabs(self, labels): return [FakeContext(self) for _ in labels]
    def expander(self, *args, **kwargs): return FakeContext(self)
    def container(self, *args, **kwargs): return FakeContext(self)
    def spinner(self, *args, **kwargs): return FakeContext(self)
    def stop(self): raise RuntimeError("streamlit stop")
    def rerun(self): raise RuntimeError("unexpected rerun")

    def text_input(self, label, value="", key=None, **kwargs):
        if key:
            self.session_state.setdefault(key, value)
            return self.session_state[key]
        return value

    def checkbox(self, label, value=False, key=None, **kwargs):
        if key:
            self.session_state.setdefault(key, value)
            return bool(self.session_state[key])
        return value

    def selectbox(self, label, options, index=0, key=None, **kwargs):
        options = list(options)
        default = options[index] if options else None
        if key:
            value = self.session_state.get(key, default)
            if value not in options:
                value = default
            self.session_state[key] = value
            return value
        return default

    def number_input(self, label, *args, value=None, key=None, **kwargs):
        if value is None:
            value = args[0] if len(args) == 1 else 0.0
        if key:
            self.session_state.setdefault(key, value)
            return self.session_state[key]
        return value

    def slider(self, label, *args, value=None, key=None, **kwargs):
        if value is None:
            value = args[2] if len(args) >= 3 else (args[0] if args else 0.0)
        if key:
            self.session_state.setdefault(key, value)
            return self.session_state[key]
        return value


def test_full_app_dry_run_without_real_streamlit(monkeypatch, tmp_path):
    fake = FakeStreamlit()
    components = types.ModuleType("streamlit.components")
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *args, **kwargs: None
    components.v1 = components_v1
    fake.components = components

    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setitem(sys.modules, "streamlit.components", components)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", components_v1)

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("bikefit_app_dry_run", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert fake.session_state["selected_bike"] == "Gravel M — przykład"
    assert fake.session_state["height"] == 1750.0
    assert fake.session_state["weight"] == 75.0

    # Integracja lokalnej wspólnej bazy z listą geometrii.
    module.COMMUNITY_BIKES_FILE = tmp_path / "community.json"
    module.save_local_bike(
        module.COMMUNITY_BIKES_FILE,
        {"name": "Wspólny test", "bike_type": "Gravel", "stack": 580.0, "reach": 390.0},
        saved_by="Tester",
    )
    module.load_local_shared_bikes_cached.clear()
    names = [bike.name for bike in module.bike_catalog()]
    assert "Wspólny test" in names


def test_base_fit_button_completes_without_blank_page(monkeypatch):
    fake = FakeStreamlit(clicked_keys={"base_fit_button"})
    components = types.ModuleType("streamlit.components")
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *args, **kwargs: None
    components.v1 = components_v1
    fake.components = components

    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setitem(sys.modules, "streamlit.components", components)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", components_v1)

    # Licznik jest osobno przetestowany; w teście UI unikamy połączenia sieciowego.
    import bikefit.visitor_counter as vc
    monkeypatch.setattr(vc, "request_counter", lambda *args, **kwargs: 1)

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("bikefit_app_base_fit", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert fake.session_state["fit_action_error"] is False
    assert "Dobrano ustawienie bazowe" in fake.session_state["fit_action_status"]
    assert 500.0 <= fake.session_state["saddle_height"] <= 900.0


def test_optimize_button_completes_without_state_error(monkeypatch):
    fake = FakeStreamlit(clicked_keys={"optimize_fit_button"})
    components = types.ModuleType("streamlit.components")
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *args, **kwargs: None
    components.v1 = components_v1
    fake.components = components

    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setitem(sys.modules, "streamlit.components", components)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", components_v1)

    import bikefit.visitor_counter as vc
    monkeypatch.setattr(vc, "request_counter", lambda *args, **kwargs: 1)

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("bikefit_app_optimize", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert fake.session_state["fit_action_error"] is False
    assert "Optymalizacja zakończona" in fake.session_state["fit_action_status"]
    assert -60.0 <= fake.session_state["saddle_fore_aft"] <= 80.0
