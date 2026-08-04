from __future__ import annotations

import math
from itertools import product

from bikefit.frame_size import assess_frame_size
from bikefit.kinematics import analyze_cycle
from bikefit.models import BikeGeometry, FitSettings, Rider
from bikefit.tire_pressure import calculate_tire_pressure


def test_configuration_matrix_is_finite_and_bounded() -> None:
    heights = [1450, 1600, 1750, 1900, 2100]
    styles = ["Komfortowa", "Zrównoważona", "Sportowa"]
    weights = [45, 75, 110, 180]
    bikes = [
        BikeGeometry(name="Road S", bike_type="Road", stack=520, reach=365, seat_tube_length=470, wheelbase=990, tire_width_front=30, tire_width_rear=30),
        BikeGeometry(name="Gravel M", bike_type="Gravel", stack=557, reach=375, seat_tube_length=520, wheelbase=1027, tire_width_front=45, tire_width_rear=45),
        BikeGeometry(name="MTB L", bike_type="MTB", stack=625, reach=470, seat_tube_length=470, wheelbase=1210, tire_width_front=60, tire_width_rear=60),
    ]

    for height, style, weight, bike in product(heights, styles, weights, bikes):
        inseam = round(height * 0.465)
        rider = Rider.from_height_inseam("Test", height, inseam, "Średnia", weight)
        settings = FitSettings(saddle_height=inseam * 0.885, style=style)
        analysis = analyze_cycle(bike, rider, settings, samples=18)
        pressure = calculate_tire_pressure(rider, bike, settings)
        frame = assess_frame_size(bike, rider, settings)

        assert math.isfinite(analysis.score)
        assert 0.0 <= analysis.score <= 100.0
        assert math.isfinite(pressure.front_bar) and pressure.front_bar > 0.0
        assert math.isfinite(pressure.rear_bar) and pressure.rear_bar > 0.0
        assert frame.title
