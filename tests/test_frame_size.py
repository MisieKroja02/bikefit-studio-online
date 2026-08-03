from bikefit.frame_size import assess_frame_size
from bikefit.models import BikeGeometry, FitSettings, Rider


def rider(height=1780.0, inseam=830.0, flexibility="Średnia"):
    return Rider.from_height_inseam("Test", height, inseam, flexibility, 80.0)


def kross_esker_m():
    return BikeGeometry(
        name="KROSS Esker 7.0 2025 M",
        bike_type="Gravel",
        stack=557.0,
        reach=375.0,
        seat_tube_length=520.0,
    )


def test_normal_frame_is_accepted():
    bike = BikeGeometry(stack=570.0, reach=380.0, seat_tube_length=520.0)
    settings = FitSettings(saddle_height=735.0, handlebar_stack_delta=10.0, handlebar_reach_delta=5.0)
    result = assess_frame_size(bike, rider(), settings)
    assert result.status == "good"


def test_large_positive_corrections_suggest_larger_frame():
    bike = BikeGeometry(stack=520.0, reach=345.0, seat_tube_length=460.0)
    settings = FitSettings(saddle_height=735.0, handlebar_stack_delta=65.0, handlebar_reach_delta=55.0)
    result = assess_frame_size(bike, rider(), settings)
    assert result.status in {"borderline_small", "too_small"}
    assert "większ" in result.suggestion.lower()


def test_large_negative_corrections_suggest_smaller_frame():
    bike = BikeGeometry(stack=640.0, reach=430.0, seat_tube_length=610.0)
    settings = FitSettings(saddle_height=735.0, handlebar_stack_delta=-55.0, handlebar_reach_delta=-50.0)
    result = assess_frame_size(bike, rider(), settings)
    assert result.status in {"borderline_large", "too_large"}
    assert "mniejsz" in result.suggestion.lower()


def test_kross_m_is_too_large_for_160_cm_rider():
    result = assess_frame_size(
        kross_esker_m(),
        rider(1600.0, 744.0, "Ograniczona"),
        FitSettings(style="Komfortowa"),
    )
    assert result.status in {"borderline_large", "too_large"}
    assert result.large_score > result.small_score


def test_kross_m_is_good_for_178_cm_rider_even_after_large_optimizer_correction():
    result = assess_frame_size(
        kross_esker_m(),
        rider(1780.0, 828.0, "Ograniczona"),
        FitSettings(style="Komfortowa", handlebar_reach_delta=-48.0, handlebar_stack_delta=28.0),
    )
    assert result.status == "good"


def test_kross_m_is_too_small_for_190_cm_rider():
    result = assess_frame_size(
        kross_esker_m(),
        rider(1900.0, 884.0, "Ograniczona"),
        FitSettings(style="Komfortowa"),
    )
    assert result.status in {"borderline_small", "too_small"}
    assert result.small_score > result.large_score


def test_assessment_changes_immediately_when_rider_height_changes():
    bike = kross_esker_m()
    settings = FitSettings(style="Zrównoważona")
    short = assess_frame_size(bike, rider(1600.0, 744.0), settings)
    medium = assess_frame_size(bike, rider(1780.0, 828.0), settings)
    tall = assess_frame_size(bike, rider(1900.0, 884.0), settings)
    assert short.status in {"borderline_large", "too_large"}
    assert medium.status == "good"
    assert tall.status in {"borderline_small", "too_small"}


def ghost_asket_m():
    # Typowa geometria gravel M; testuje również rozmiar zakodowany w nazwie.
    return BikeGeometry(
        name="Ghost_Asket CF Pro_2025_M",
        bike_type="Gravel",
        stack=555.0,
        reach=385.0,
        seat_tube_length=500.0,
    )


def test_named_m_gravel_is_not_accepted_for_155_cm():
    result = assess_frame_size(
        ghost_asket_m(),
        rider(1550.0, 721.0, "Ograniczona"),
        FitSettings(style="Komfortowa", handlebar_stack_delta=16.0, handlebar_reach_delta=-4.0),
    )
    assert result.status == "too_large"
    assert result.large_score > result.small_score
    assert any("rozmiar M" in reason for reason in result.reasons)


def test_named_m_gravel_is_not_accepted_for_160_cm():
    result = assess_frame_size(
        ghost_asket_m(),
        rider(1600.0, 744.0, "Ograniczona"),
        FitSettings(style="Komfortowa", handlebar_stack_delta=28.0, handlebar_reach_delta=6.0),
    )
    assert result.status in {"borderline_large", "too_large"}
    assert result.large_score > result.small_score


def test_named_m_gravel_remains_good_near_178_cm():
    result = assess_frame_size(
        ghost_asket_m(),
        rider(1780.0, 828.0, "Ograniczona"),
        FitSettings(style="Komfortowa"),
    )
    assert result.status == "good"
