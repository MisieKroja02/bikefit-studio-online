from __future__ import annotations

from dataclasses import dataclass
import math

from .models import BikeGeometry, FitSettings, Rider


BAR_TO_PSI = 14.5037738


@dataclass
class TirePressureResult:
    total_mass: float
    front_load: float
    rear_load: float
    front_bar: float
    rear_bar: float
    front_psi: float
    rear_psi: float
    front_low: float
    front_high: float
    rear_low: float
    rear_high: float
    warning: str


SURFACE_FACTORS = {
    "Gładki asfalt": 0.79,
    "Typowy asfalt": 0.74,
    "Szorstki asfalt": 0.68,
    "Mieszany asfalt/szuter": 0.63,
    "Szuter": 0.59,
    "Teren / leśne drogi": 0.55,
}

SETUP_FACTORS = {
    "Dętka butylowa": 1.04,
    "Dętka TPU": 1.01,
    "Dętka lateksowa": 0.99,
    "Tubeless": 0.94,
}

CASING_FACTORS = {
    "Elastyczny": 0.96,
    "Standard": 1.00,
    "Wzmocniony": 1.05,
}

GOAL_OFFSETS_BAR = {
    "Komfort": -0.10,
    "Zrównoważone": 0.00,
    "Ochrona obręczy": 0.15,
}


def suggested_front_load_percent(bike_type: str, style: str) -> float:
    bike_type = (bike_type or "Gravel").lower()
    base = 44.0
    if bike_type in ("road", "szosa", "tt", "triathlon"):
        base = 45.5
    elif bike_type in ("mtb", "mountain"):
        base = 42.0
    elif bike_type in ("trekking", "city", "urban"):
        base = 43.0
    if style == "Komfortowa":
        base -= 1.0
    elif style == "Sportowa":
        base += 1.0
    return max(38.0, min(50.0, base))


def _pressure_from_load(load_kg: float, width_mm: float, surface_factor: float) -> float:
    """Physics-inspired start pressure.

    First estimates a pressure for an average wheel and then load split is softened
    in calculate_tire_pressure. Width is the measured tyre width, not just the label.
    """
    load_lb = load_kg * 2.20462262
    width_in = max(0.75, width_mm / 25.4)
    psi = surface_factor * load_lb / (width_in ** 1.5)
    return psi / BAR_TO_PSI


def calculate_tire_pressure(
    rider: Rider,
    bike: BikeGeometry,
    settings: FitSettings,
) -> TirePressureResult:
    total_mass = max(35.0, rider.weight + bike.bike_weight + settings.gear_weight)
    front_fraction = max(0.35, min(0.50, settings.front_load_percent / 100.0))
    front_load = total_mass * front_fraction
    rear_load = total_mass - front_load
    average_load = total_mass / 2.0

    surface_factor = SURFACE_FACTORS.get(settings.tire_surface, 0.74)
    setup_factor = SETUP_FACTORS.get(settings.tire_setup, 1.0)
    casing_factor = CASING_FACTORS.get(settings.tire_casing, 1.0)
    goal_offset = GOAL_OFFSETS_BAR.get(settings.pressure_goal, 0.0)

    # Pressure split is intentionally softer than the raw static load split.
    # This better reflects real-world calculators and avoids an excessive
    # front/rear gap for wide tyres.
    front_base = _pressure_from_load(average_load, bike.tire_width_front, surface_factor)
    rear_base = _pressure_from_load(average_load, bike.tire_width_rear, surface_factor)
    front_ratio = (front_load / average_load) ** 0.65
    rear_ratio = (rear_load / average_load) ** 0.65

    front_bar = front_base * front_ratio * setup_factor * casing_factor + goal_offset
    rear_bar = rear_base * rear_ratio * setup_factor * casing_factor + goal_offset

    # Minimums protect against unrealistic outputs. Tubeless can safely start lower
    # than tubes, but real rim/tyre limits always have priority.
    tube_setup = settings.tire_setup != "Tubeless"
    min_front = 1.25 if not tube_setup else 1.05
    min_rear = 1.35 if not tube_setup else 1.15
    front_bar = max(min_front, front_bar)
    rear_bar = max(min_rear, rear_bar)

    warning_parts: list[str] = []
    max_pressure = max(1.5, bike.tire_max_pressure)
    if front_bar > max_pressure or rear_bar > max_pressure:
        warning_parts.append(
            f"Wynik przekracza ustawiony limit {max_pressure:.1f} bar — sprawdź limit opony i obręczy."
        )
    front_bar = min(front_bar, max_pressure)
    rear_bar = min(rear_bar, max_pressure)

    if bike.tire_width_front < 23 or bike.tire_width_rear < 23:
        warning_parts.append("Bardzo wąska opona: wynik wymaga szczególnej kontroli zakresu producenta.")
    if total_mass > 140:
        warning_parts.append("Duża masa systemowa: sprawdź również dopuszczalne obciążenie opon i kół.")
    if not warning_parts:
        warning_parts.append("To ciśnienie startowe; skoryguj je po jeździe testowej o około 0,1–0,2 bar.")

    spread = 0.15
    return TirePressureResult(
        total_mass=total_mass,
        front_load=front_load,
        rear_load=rear_load,
        front_bar=front_bar,
        rear_bar=rear_bar,
        front_psi=front_bar * BAR_TO_PSI,
        rear_psi=rear_bar * BAR_TO_PSI,
        front_low=max(0.8, front_bar - spread),
        front_high=min(max_pressure, front_bar + spread),
        rear_low=max(0.8, rear_bar - spread),
        rear_high=min(max_pressure, rear_bar + spread),
        warning=" ".join(warning_parts),
    )
