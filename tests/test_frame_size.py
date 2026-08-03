from bikefit.frame_size import assess_frame_size
from bikefit.models import BikeGeometry, FitSettings, Rider


def rider():
    return Rider.from_height_inseam("Test", 1780.0, 830.0, "Średnia", 80.0)


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
