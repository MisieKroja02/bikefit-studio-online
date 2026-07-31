from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .models import BikeGeometry, FitSettings, Rider

Point = Tuple[float, float]


@dataclass
class Pose:
    phase_deg: float
    bb: Point
    pedal: Point
    ankle: Point
    knee: Optional[Point]
    hip: Point
    shoulder: Optional[Point]
    elbow: Optional[Point]
    hand: Point
    saddle: Point
    knee_flexion: Optional[float]
    hip_angle: Optional[float]
    elbow_angle: Optional[float]
    torso_angle: Optional[float]
    reachable_leg: bool
    reachable_arm: bool


@dataclass
class CycleAnalysis:
    score: float
    knee_flexion_min: float
    knee_flexion_max: float
    hip_angle_min: float
    hip_angle_max: float
    elbow_angle: float
    torso_angle: float
    unreachable_samples: int
    messages: List[str]


def add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1]


def sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def mul(a: Point, scalar: float) -> Point:
    return a[0] * scalar, a[1] * scalar


def length(v: Point) -> float:
    return math.hypot(v[0], v[1])


def distance(a: Point, b: Point) -> float:
    return length(sub(a, b))


def angle_between(v1: Point, v2: Point) -> float:
    l1 = length(v1)
    l2 = length(v2)
    if l1 <= 1e-9 or l2 <= 1e-9:
        return 0.0
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
    return math.degrees(math.acos(c))


def joint_angle(a: Point, joint: Point, b: Point) -> float:
    return angle_between(sub(a, joint), sub(b, joint))


def circle_intersections(c0: Point, r0: float, c1: Point, r1: float) -> List[Point]:
    d = distance(c0, c1)
    if d <= 1e-9 or d > r0 + r1 or d < abs(r0 - r1):
        return []
    a = (r0 * r0 - r1 * r1 + d * d) / (2.0 * d)
    h2 = max(0.0, r0 * r0 - a * a)
    h = math.sqrt(h2)
    x2 = c0[0] + a * (c1[0] - c0[0]) / d
    y2 = c0[1] + a * (c1[1] - c0[1]) / d
    rx = -(c1[1] - c0[1]) * h / d
    ry = (c1[0] - c0[0]) * h / d
    return [(x2 + rx, y2 + ry), (x2 - rx, y2 - ry)]


def style_targets(style: str) -> Dict[str, float]:
    if style == "Komfortowa":
        return {"torso": 47.0, "elbow": 150.0, "hip_min": 55.0}
    if style == "Sportowa":
        return {"torso": 27.0, "elbow": 158.0, "hip_min": 45.0}
    return {"torso": 36.0, "elbow": 154.0, "hip_min": 50.0}


def bike_points(geometry: BikeGeometry, settings: FitSettings) -> Dict[str, Point]:
    sta = math.radians(geometry.seat_tube_angle)
    hta = math.radians(geometry.head_tube_angle)
    saddle_axis = (
        -settings.saddle_height * math.cos(sta),
        settings.saddle_height * math.sin(sta),
    )
    # saddle_fore_aft: dodatnia wartość przesuwa siodło do przodu.
    saddle = (saddle_axis[0] + settings.saddle_fore_aft, saddle_axis[1])

    head_top = (
        geometry.reach + settings.handlebar_reach_delta,
        geometry.stack + settings.handlebar_stack_delta,
    )
    head_bottom = (
        head_top[0] - geometry.head_tube_length * math.cos(hta),
        head_top[1] - geometry.head_tube_length * math.sin(hta),
    )
    stem_angle = math.radians(geometry.stem_angle)
    stem_end = (
        head_top[0] + geometry.stem_length * math.cos(stem_angle),
        head_top[1] + geometry.stem_length * math.sin(stem_angle),
    )
    hand = (stem_end[0] + geometry.hood_reach, stem_end[1] - 18.0)

    rear_x = math.sqrt(max(1.0, geometry.chainstay ** 2 - geometry.bb_drop ** 2))
    rear_axle = (-rear_x, geometry.bb_drop)
    front_axle = (geometry.wheelbase - rear_x, geometry.bb_drop)

    seat_top = (
        -geometry.seat_tube_length * math.cos(sta),
        geometry.seat_tube_length * math.sin(sta),
    )
    return {
        "bb": (0.0, 0.0),
        "saddle": saddle,
        "head_top": head_top,
        "head_bottom": head_bottom,
        "stem_end": stem_end,
        "hand": hand,
        "rear_axle": rear_axle,
        "front_axle": front_axle,
        "seat_top": seat_top,
    }


def solve_leg(hip: Point, ankle: Point, thigh: float, shank: float) -> Optional[Point]:
    points = circle_intersections(hip, thigh, ankle, shank)
    if not points:
        return None
    # Kolano rowerzysty powinno znaleźć się przed linią biodro–kostka.
    return max(points, key=lambda p: (p[0], -p[1]))


def solve_arm(shoulder: Point, hand: Point, upper: float, forearm: float) -> Optional[Point]:
    points = circle_intersections(shoulder, upper, hand, forearm)
    if not points:
        return None
    # Łokieć zwykle jest poniżej barku i lekko cofnięty względem dłoni.
    return min(points, key=lambda p: (p[1] + 0.15 * p[0]))


def choose_upper_body(
    hip: Point,
    hand: Point,
    rider: Rider,
    style: str,
) -> Tuple[Optional[Point], Optional[Point], Optional[float], Optional[float]]:
    target = style_targets(style)
    best = None
    for torso_angle in [15.0 + i * 0.5 for i in range(111)]:
        rad = math.radians(torso_angle)
        shoulder = (
            hip[0] + rider.torso * math.cos(rad),
            hip[1] + rider.torso * math.sin(rad),
        )
        elbow = solve_arm(shoulder, hand, rider.upper_arm, rider.forearm)
        if elbow is None:
            continue
        elbow_angle = joint_angle(shoulder, elbow, hand)
        cost = ((torso_angle - target["torso"]) / 8.0) ** 2 + ((elbow_angle - target["elbow"]) / 12.0) ** 2
        if best is None or cost < best[0]:
            best = (cost, shoulder, elbow, elbow_angle, torso_angle)
    if best is None:
        return None, None, None, None
    return best[1], best[2], best[3], best[4]


def calculate_pose(
    geometry: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
    phase_deg: float,
) -> Pose:
    points = bike_points(geometry, settings)
    bb = points["bb"]
    phase = math.radians(phase_deg)
    pedal = (
        geometry.crank_length * math.cos(phase),
        geometry.crank_length * math.sin(phase),
    )

    foot_angle = math.radians(settings.foot_angle)
    ankle_to_cleat = (
        rider.ankle_to_cleat * math.cos(foot_angle),
        rider.ankle_to_cleat * math.sin(foot_angle),
    )
    ankle = sub(pedal, ankle_to_cleat)

    # Staw biodrowy znajduje się przed i poniżej punktu podparcia na siodle.
    hip = add(points["saddle"], (38.0, -48.0))
    knee = solve_leg(hip, ankle, rider.thigh, rider.shank)
    shoulder, elbow, elbow_angle, torso_angle = choose_upper_body(hip, points["hand"], rider, settings.style)

    knee_flexion = None
    hip_angle = None
    if knee is not None:
        knee_flexion = 180.0 - joint_angle(hip, knee, ankle)
        if shoulder is not None:
            hip_angle = joint_angle(shoulder, hip, knee)

    return Pose(
        phase_deg=phase_deg,
        bb=bb,
        pedal=pedal,
        ankle=ankle,
        knee=knee,
        hip=hip,
        shoulder=shoulder,
        elbow=elbow,
        hand=points["hand"],
        saddle=points["saddle"],
        knee_flexion=knee_flexion,
        hip_angle=hip_angle,
        elbow_angle=elbow_angle,
        torso_angle=torso_angle,
        reachable_leg=knee is not None,
        reachable_arm=shoulder is not None and elbow is not None,
    )


def _range_penalty(value: float, low: float, high: float, softness: float = 1.0) -> float:
    if low <= value <= high:
        center = (low + high) / 2.0
        half = max((high - low) / 2.0, 1e-6)
        return 0.08 * ((value - center) / half) ** 2
    delta = low - value if value < low else value - high
    return (delta / softness) ** 2


def analyze_cycle(
    geometry: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
    samples: int = 72,
) -> CycleAnalysis:
    poses = [calculate_pose(geometry, rider, settings, i * 360.0 / samples) for i in range(samples)]
    valid = [p for p in poses if p.knee_flexion is not None and p.hip_angle is not None]
    unreachable = samples - len(valid)
    target = style_targets(settings.style)

    if not valid:
        return CycleAnalysis(
            score=0.0,
            knee_flexion_min=0.0,
            knee_flexion_max=0.0,
            hip_angle_min=0.0,
            hip_angle_max=0.0,
            elbow_angle=0.0,
            torso_angle=0.0,
            unreachable_samples=samples,
            messages=["Noga nie dosięga pedału w obecnej geometrii."],
        )

    knees = [p.knee_flexion for p in valid if p.knee_flexion is not None]
    hips = [p.hip_angle for p in valid if p.hip_angle is not None]
    arm_pose = next((p for p in valid if p.elbow_angle is not None), None)
    elbow = arm_pose.elbow_angle if arm_pose and arm_pose.elbow_angle is not None else 0.0
    torso = arm_pose.torso_angle if arm_pose and arm_pose.torso_angle is not None else 0.0

    knee_min = min(knees)
    knee_max = max(knees)
    hip_min = min(hips)
    hip_max = max(hips)

    penalty = 0.0
    penalty += 2.4 * _range_penalty(knee_min, 25.0, 35.0, 2.5)
    penalty += 0.65 * _range_penalty(knee_max, 98.0, 125.0, 6.0)
    penalty += 0.7 * _range_penalty(hip_min, target["hip_min"], 82.0, 5.0)
    if elbow:
        penalty += 0.45 * _range_penalty(elbow, 142.0, 168.0, 5.0)
    else:
        penalty += 20.0
    if torso:
        penalty += 0.35 * ((torso - target["torso"]) / 9.0) ** 2
    penalty += unreachable * 3.0

    score = max(0.0, min(100.0, 100.0 - 7.5 * math.sqrt(max(0.0, penalty))))
    messages: List[str] = []
    if unreachable:
        messages.append(f"Brak rozwiązania nogi dla {unreachable}/{samples} pozycji korby.")
    if knee_min < 25.0:
        messages.append("Noga jest zbyt wyprostowana: rozważ obniżenie siodła.")
    elif knee_min > 35.0:
        messages.append("Noga pozostaje mocno zgięta: rozważ podniesienie siodła.")
    else:
        messages.append("Wyprost kolana mieści się w przyjętym zakresie startowym 25–35°.")
    if hip_min < target["hip_min"]:
        messages.append("Kąt biodra jest mocno zamknięty: podnieś kierownicę lub skróć zasięg.")
    if elbow and elbow > 170.0:
        messages.append("Ręce są prawie zablokowane: skróć zasięg do kierownicy.")
    elif elbow and elbow < 140.0:
        messages.append("Łokcie są mocno ugięte: zasięg może być za krótki.")
    if not messages:
        messages.append("Ustawienie nie przekracza podstawowych progów modelu.")

    return CycleAnalysis(
        score=score,
        knee_flexion_min=knee_min,
        knee_flexion_max=knee_max,
        hip_angle_min=hip_min,
        hip_angle_max=hip_max,
        elbow_angle=elbow,
        torso_angle=torso,
        unreachable_samples=unreachable,
        messages=messages,
    )
