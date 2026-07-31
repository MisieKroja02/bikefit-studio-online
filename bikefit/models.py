from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict


@dataclass
class BikeGeometry:
    name: str = "KROSS Esker 7.0 2025 M"
    bike_type: str = "Gravel"
    stack: float = 557.0
    reach: float = 375.0
    seat_tube_angle: float = 74.0
    head_tube_angle: float = 71.0
    head_tube_length: float = 140.0
    seat_tube_length: float = 520.0
    top_tube: float = 535.0
    bb_drop: float = 67.0
    chainstay: float = 435.0
    wheelbase: float = 1027.0
    fork_offset: float = 46.0
    wheel_radius: float = 356.0
    stem_length: float = 80.0
    stem_angle: float = -7.0
    hood_reach: float = 75.0
    crank_length: float = 172.5
    bike_weight: float = 10.8
    tire_width_front: float = 45.0
    tire_width_rear: float = 45.0
    tire_max_pressure: float = 4.5

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BikeGeometry":
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in payload.items() if k in allowed}
        return cls(**values)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Rider:
    name: str = "Robert"
    height: float = 1780.0
    inseam: float = 830.0
    weight: float = 101.0
    flexibility: str = "Średnia"
    thigh: float = 462.0
    shank: float = 418.0
    torso: float = 505.0
    upper_arm: float = 326.0
    forearm: float = 258.0
    foot: float = 270.0
    ankle_to_cleat: float = 112.0

    @classmethod
    def from_height_inseam(
        cls,
        name: str,
        height: float,
        inseam: float,
        flexibility: str = "Średnia",
        weight: float = 101.0,
    ) -> "Rider":
        # Proporcje są przybliżeniem antropometrycznym do symulacji 2D.
        leg_joint_length = inseam * 1.02
        return cls(
            name=name,
            height=height,
            inseam=inseam,
            weight=weight,
            flexibility=flexibility,
            thigh=leg_joint_length * 0.525,
            shank=leg_joint_length * 0.475,
            torso=height * 0.284,
            upper_arm=height * 0.183,
            forearm=height * 0.145,
            foot=height * 0.152,
            ankle_to_cleat=height * 0.063,
        )

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Rider":
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in payload.items() if k in allowed}
        return cls(**values)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FitSettings:
    saddle_height: float = 738.0
    saddle_fore_aft: float = 0.0
    handlebar_stack_delta: float = 0.0
    handlebar_reach_delta: float = 0.0
    cadence: float = 85.0
    foot_angle: float = -8.0
    style: str = "Zrównoważona"
    gear_weight: float = 1.5
    tire_setup: str = "Tubeless"
    tire_surface: str = "Typowy asfalt"
    tire_casing: str = "Standard"
    pressure_goal: str = "Zrównoważone"
    front_load_percent: float = 44.0

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FitSettings":
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in payload.items() if k in allowed}
        return cls(**values)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
