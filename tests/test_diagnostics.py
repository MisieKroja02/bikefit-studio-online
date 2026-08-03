from bikefit.diagnostics import explain_fit
from bikefit.kinematics import analyze_cycle
from bikefit.models import BikeGeometry, FitSettings, Rider
from bikefit.recommendations import base_recommendation


def setup_values():
    bike = BikeGeometry()
    rider = Rider.from_height_inseam("Test", 1780.0, 830.0, "Średnia", 80.0)
    base = base_recommendation(rider, bike, "Zrównoważona", "Średnia").settings
    return bike, rider, base


def test_high_saddle_explains_overextension():
    bike, rider, base = setup_values()
    settings = FitSettings.from_dict({**base.to_dict(), "saddle_height": base.saddle_height + 55.0})
    analysis = analyze_cycle(bike, rider, settings)
    diagnostics = explain_fit(bike, rider, settings, analysis)
    assert analysis.score < 90
    assert any(item.area == "Wysokość siodła" and "za wysoko" in item.title.lower() for item in diagnostics)


def test_low_saddle_explains_excessive_flexion():
    bike, rider, base = setup_values()
    settings = FitSettings.from_dict({**base.to_dict(), "saddle_height": base.saddle_height - 70.0})
    analysis = analyze_cycle(bike, rider, settings)
    diagnostics = explain_fit(bike, rider, settings, analysis)
    assert analysis.score < 90
    assert any(item.area in {"Wysokość siodła", "Zgięcie kolana u góry"} for item in diagnostics)


def test_long_cockpit_explains_arm_or_hip_issue():
    bike, rider, base = setup_values()
    settings = FitSettings.from_dict({
        **base.to_dict(),
        "handlebar_reach_delta": 75.0,
        "handlebar_stack_delta": -55.0,
    })
    analysis = analyze_cycle(bike, rider, settings)
    diagnostics = explain_fit(bike, rider, settings, analysis, threshold=99.0)
    assert analysis.score < 99
    assert any(item.area in {"Zasięg kierownicy", "Otwarcie biodra", "Pochylenie tułowia"} for item in diagnostics)


def test_good_score_has_no_warning_diagnostics():
    bike, rider, base = setup_values()
    analysis = analyze_cycle(bike, rider, base)
    diagnostics = explain_fit(bike, rider, base, analysis)
    if analysis.score >= 90:
        assert diagnostics == []
