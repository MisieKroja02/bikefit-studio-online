from __future__ import annotations

import unittest

from bikefit.internet_import import _extract_from_text
from bikefit.kinematics import analyze_cycle, angle_between, calculate_pose
from bikefit.models import BikeGeometry, FitSettings, Rider
from bikefit.optimizer import optimize_fit
from bikefit.tire_pressure import calculate_tire_pressure


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bike = BikeGeometry()
        self.rider = Rider.from_height_inseam("Test", 1780, 830)
        self.settings = FitSettings()

    def test_angle_between(self) -> None:
        self.assertAlmostEqual(angle_between((1, 0), (0, 1)), 90.0, places=6)

    def test_pose_is_reachable_for_default_profile(self) -> None:
        pose = calculate_pose(self.bike, self.rider, self.settings, 270.0)
        self.assertTrue(pose.reachable_leg)
        self.assertIsNotNone(pose.knee_flexion)

    def test_cycle_score_is_finite(self) -> None:
        analysis = analyze_cycle(self.bike, self.rider, self.settings)
        self.assertGreaterEqual(analysis.score, 0.0)
        self.assertLessEqual(analysis.score, 100.0)

    def test_optimizer_does_not_reduce_raw_score_materially(self) -> None:
        before = analyze_cycle(self.bike, self.rider, self.settings).score
        result, after = optimize_fit(self.bike, self.rider, self.settings)
        self.assertGreaterEqual(after.score + 1.0, before)
        self.assertGreater(result.saddle_height, 600)

    def test_html_geometry_parser(self) -> None:
        text = "Stack: 557 mm Reach 375 mm Seat Tube Angle 74 deg Wheelbase 1027 mm BB Drop 67 mm"
        result = _extract_from_text(text)
        self.assertEqual(result["stack"], 557.0)
        self.assertEqual(result["reach"], 375.0)
        self.assertEqual(result["seat_tube_angle"], 74.0)

    def test_tire_pressure_uses_weight_and_width(self) -> None:
        pressure = calculate_tire_pressure(self.rider, self.bike, self.settings)
        self.assertGreater(pressure.front_bar, 1.0)
        self.assertGreater(pressure.rear_bar, pressure.front_bar)
        wider_bike = BikeGeometry(tire_width_front=50.0, tire_width_rear=50.0)
        wider = calculate_tire_pressure(self.rider, wider_bike, self.settings)
        self.assertLess(wider.front_bar, pressure.front_bar)


if __name__ == "__main__":
    unittest.main()
