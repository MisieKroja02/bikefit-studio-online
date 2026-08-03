from pathlib import Path


def test_release_has_new_geometry_source_and_no_99spokes() -> None:
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "https://www.bike-stats.de/en/" in app
    assert "99spokes.com" not in app.lower()


def test_release_contains_persistent_geometry_hooks() -> None:
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "persist_shared_geometry" in app
    assert "load_shared_geometry_payloads" in app
    assert 'selected_bike": "Gravel M — przykład"' in app


def test_import_flow_allows_custom_geometry_name_before_shared_save() -> None:
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"Proponowana nazwa geometrii (opcjonalnie)"' in app
    assert '"Nazwa zapisywanej geometrii"' in app
    assert '"Zapisz i zastosuj"' in app
    assert "imported_geometry_with_name" in app
