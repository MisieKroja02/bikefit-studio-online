from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict, Tuple

from .kinematics import CycleAnalysis, analyze_cycle
from .models import BikeGeometry, FitSettings, Rider

ProgressCallback = Callable[[str], None]


BOUNDS: Dict[str, Tuple[float, float]] = {
    "saddle_height": (620.0, 850.0),
    "saddle_fore_aft": (-60.0, 80.0),
    "handlebar_stack_delta": (-60.0, 100.0),
    "handlebar_reach_delta": (-80.0, 80.0),
}


def _clamp(name: str, value: float) -> float:
    low, high = BOUNDS[name]
    return max(low, min(high, value))


def optimize_fit(
    geometry: BikeGeometry,
    rider: Rider,
    initial: FitSettings,
    progress: ProgressCallback | None = None,
) -> tuple[FitSettings, CycleAnalysis]:
    """Deterministyczne przeszukiwanie współrzędnych, bez bibliotek zewnętrznych."""
    current = replace(initial)
    current_analysis = analyze_cycle(geometry, rider, current, samples=72)
    reference = replace(initial)

    def objective(settings: FitSettings) -> tuple[float, CycleAnalysis]:
        analysis = analyze_cycle(geometry, rider, settings, samples=72)
        # Lekka kara za duże zmiany, aby wynik był praktyczny, a nie tylko matematyczny.
        regularization = (
            ((settings.saddle_height - reference.saddle_height) / 35.0) ** 2
            + ((settings.saddle_fore_aft - reference.saddle_fore_aft) / 30.0) ** 2
            + ((settings.handlebar_stack_delta - reference.handlebar_stack_delta) / 45.0) ** 2
            + ((settings.handlebar_reach_delta - reference.handlebar_reach_delta) / 45.0) ** 2
        )
        return analysis.score - 0.7 * regularization, analysis

    current_obj, current_analysis = objective(current)
    variables = (
        "saddle_height",
        "saddle_fore_aft",
        "handlebar_stack_delta",
        "handlebar_reach_delta",
    )

    for step in (16.0, 8.0, 4.0, 2.0, 1.0):
        improved = True
        passes = 0
        while improved and passes < 4:
            improved = False
            passes += 1
            for name in variables:
                base = getattr(current, name)
                candidates = [base + direction * step for direction in (-2, -1, 1, 2)]
                best_local = (current_obj, current, current_analysis)
                for value in candidates:
                    candidate = replace(current, **{name: _clamp(name, value)})
                    obj, analysis = objective(candidate)
                    if obj > best_local[0] + 1e-7:
                        best_local = (obj, candidate, analysis)
                if best_local[1] is not current:
                    current_obj, current, current_analysis = best_local
                    improved = True
            if progress:
                progress(f"Krok {step:.0f} mm, ocena {current_analysis.score:.1f}/100")

    return current, current_analysis
