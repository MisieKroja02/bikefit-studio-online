from __future__ import annotations

from dataclasses import dataclass
import re

from .models import BikeGeometry, FitSettings, Rider


@dataclass(frozen=True)
class FrameSizeAssessment:
    status: str
    title: str
    summary: str
    reasons: tuple[str, ...]
    suggestion: str
    confidence: str
    small_score: float
    large_score: float

    @property
    def color(self) -> str:
        return {
            "good": "#67e4b5",
            "borderline_small": "#ffd166",
            "borderline_large": "#ffd166",
            "too_small": "#ff9f5a",
            "too_large": "#ff7f91",
        }.get(self.status, "#9db3c7")


@dataclass(frozen=True)
class _TargetGeometry:
    stack: float
    reach: float
    seat_tube: float


_SIZE_HEIGHT_BANDS: dict[str, dict[str, tuple[float, float]]] = {
    # Zakresy są celowo szerokie. Służą jako kontrola zdroworozsądkowa
    # oznaczenia producenta, a nie jako zamiennik tabeli rozmiarów konkretnej marki.
    "road_gravel": {
        "XXS": (1420.0, 1570.0),
        "XS": (1500.0, 1650.0),
        "S": (1580.0, 1740.0),
        "M": (1680.0, 1850.0),
        "L": (1780.0, 1940.0),
        "XL": (1880.0, 2030.0),
        "XXL": (1970.0, 2120.0),
    },
    "mtb": {
        "XXS": (1400.0, 1540.0),
        "XS": (1480.0, 1620.0),
        "S": (1550.0, 1700.0),
        "M": (1650.0, 1810.0),
        "L": (1750.0, 1910.0),
        "XL": (1850.0, 2010.0),
        "XXL": (1940.0, 2110.0),
    },
    "city": {
        "XXS": (1420.0, 1570.0),
        "XS": (1500.0, 1650.0),
        "S": (1580.0, 1740.0),
        "M": (1680.0, 1850.0),
        "L": (1780.0, 1950.0),
        "XL": (1880.0, 2050.0),
        "XXL": (1980.0, 2140.0),
    },
}


def _size_family(bike_type: str) -> str:
    kind = (bike_type or "").strip().lower()
    if kind in {"mtb", "mountain"}:
        return "mtb"
    if kind in {"trekking", "city", "urban"}:
        return "city"
    return "road_gravel"


def _extract_named_size(name: str) -> str | None:
    """Rozpoznaje rozmiar tekstowy zapisany w nazwie geometrii.

    Obsługuje m.in. ``Ghost_Asket_2025_M``, ``KROSS Esker M`` oraz ``size-L``.
    Kolejność od najdłuższego tokenu chroni przed rozpoznaniem ``XL`` jako ``L``.
    """
    normalized = re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).strip()
    tokens = normalized.split()
    for size in ("XXL", "XXS", "XL", "XS", "L", "M", "S"):
        if size in tokens:
            return size
    return None


def _named_size_signal(bike: BikeGeometry, rider: Rider) -> tuple[float, float, list[str], list[str]]:
    """Zwraca dodatkowy sygnał za małej/za dużej ramy z oznaczenia rozmiaru.

    Jest to bezpiecznik dla oczywistych przypadków, np. 155 cm na ramie M.
    Wewnątrz szerokiego zakresu nie dodaje żadnych punktów.
    """
    size = _extract_named_size(bike.name)
    if not size:
        return 0.0, 0.0, [], []
    band = _SIZE_HEIGHT_BANDS[_size_family(bike.bike_type)].get(size)
    if not band:
        return 0.0, 0.0, [], []

    low, high = band
    height = float(rider.height)
    small_score = 0.0
    large_score = 0.0
    small_reasons: list[str] = []
    large_reasons: list[str] = []

    if height < low:
        outside = low - height
        # 30 mm poza zakresem = sygnał graniczny; 100+ mm = silny sygnał.
        large_score = 1.25 + min(5.0, outside / 28.0)
        large_reasons.append(
            f"Geometria jest oznaczona jako rozmiar {size}. Dla wzrostu {height/10:.0f} cm jest to wyraźnie poniżej "
            f"szerokiego orientacyjnego zakresu tego oznaczenia ({low/10:.0f}–{high/10:.0f} cm)."
        )
    elif height > high:
        outside = height - high
        small_score = 1.25 + min(5.0, outside / 28.0)
        small_reasons.append(
            f"Geometria jest oznaczona jako rozmiar {size}. Dla wzrostu {height/10:.0f} cm jest to powyżej "
            f"szerokiego orientacyjnego zakresu tego oznaczenia ({low/10:.0f}–{high/10:.0f} cm)."
        )

    return small_score, large_score, small_reasons, large_reasons


def _bike_ratios(bike_type: str) -> tuple[float, float, float]:
    """Zwraca bazowe proporcje: stack/wzrost, reach/wzrost, rura/przekrok.

    Są to orientacyjne środki zakresów używane wyłącznie do porównania
    sąsiednich rozmiarów. Nie zastępują tabeli producenta.
    """
    kind = (bike_type or "").strip().lower()
    if kind in {"road", "szosa"}:
        return 0.305, 0.215, 0.610
    if kind in {"mtb", "mountain"}:
        return 0.342, 0.245, 0.505
    if kind in {"trekking", "city", "urban"}:
        return 0.350, 0.214, 0.625
    if kind in {"tt", "triathlon"}:
        return 0.286, 0.226, 0.600
    # Gravel / przełaj.
    return 0.313, 0.211, 0.620


def _target_geometry(bike: BikeGeometry, rider: Rider, settings: FitSettings) -> _TargetGeometry:
    height = max(1400.0, float(rider.height))
    inseam = max(600.0, float(rider.inseam))
    stack_ratio, reach_ratio, seat_ratio = _bike_ratios(bike.bike_type)

    # Dłuższe nogi zwykle oznaczają relatywnie krótszy tułów: trochę większy
    # docelowy stack i trochę mniejszy reach. Krótsze nogi działają odwrotnie.
    expected_inseam = height * 0.465
    leg_delta = inseam - expected_inseam

    target_stack = height * stack_ratio + leg_delta * 0.34
    target_reach = height * reach_ratio - leg_delta * 0.22
    target_seat_tube = inseam * seat_ratio

    style = (settings.style or "Zrównoważona").lower()
    if style.startswith("komfort"):
        target_stack += 15.0
        target_reach -= 6.0
    elif style.startswith("sport"):
        target_stack -= 12.0
        target_reach += 5.0

    flexibility = (rider.flexibility or "Średnia").lower()
    if flexibility.startswith("ogran"):
        target_stack += 8.0
        target_reach -= 3.0
    elif flexibility.startswith("dobra"):
        target_stack -= 4.0
        target_reach += 2.0

    return _TargetGeometry(target_stack, target_reach, target_seat_tube)


def _axis_score(delta: float, neutral: float, severe: float) -> float:
    """Punktacja różnicy wymiaru; znak określa kierunek rozmiaru.

    delta > 0: geometria większa od celu. delta < 0: geometria mniejsza.
    """
    magnitude = abs(float(delta))
    if magnitude <= neutral:
        return 0.0
    if magnitude >= severe:
        return 3.0 + (magnitude - severe) / max(20.0, severe)
    return 0.65 + 2.35 * (magnitude - neutral) / (severe - neutral)


def _append_axis_reason(
    *,
    delta: float,
    value: float,
    target: float,
    label: str,
    small_reasons: list[str],
    large_reasons: list[str],
) -> None:
    if delta < 0:
        small_reasons.append(
            f"{label} ramy wynosi {value:.0f} mm, a orientacyjny środek zakresu dla tych danych to około {target:.0f} mm. "
            "Rama jest w tym wymiarze mniejsza od punktu odniesienia."
        )
    elif delta > 0:
        large_reasons.append(
            f"{label} ramy wynosi {value:.0f} mm, a orientacyjny środek zakresu dla tych danych to około {target:.0f} mm. "
            "Rama jest w tym wymiarze większa od punktu odniesienia."
        )


def assess_frame_size(
    bike: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
) -> FrameSizeAssessment:
    """Ocena rozmiaru ramy aktualizowana bezpośrednio z danych użytkownika.

    Najpierw analizowana jest sama geometria (stack, reach i rura podsiodłowa)
    względem wzrostu i przekroku. Korekty kokpitu są tylko sygnałem pomocniczym
    i nie mogą samodzielnie zmienić dobrze dobranej ramy w "za dużą" lub "za małą".
    """

    target = _target_geometry(bike, rider, settings)
    stack_delta = float(bike.stack) - target.stack
    reach_delta = float(bike.reach) - target.reach
    seat_delta = float(bike.seat_tube_length) - target.seat_tube

    small_score = 0.0
    large_score = 0.0
    small_reasons: list[str] = []
    large_reasons: list[str] = []

    # Oznaczenie rozmiaru (np. M) jest niezależnym bezpiecznikiem dla
    # oczywistych niedopasowań. Nie wpływa na wynik wewnątrz szerokiego pasma.
    size_small, size_large, size_small_reasons, size_large_reasons = _named_size_signal(bike, rider)
    small_score += size_small
    large_score += size_large
    small_reasons.extend(size_small_reasons)
    large_reasons.extend(size_large_reasons)

    # Reach jest najsilniejszym sygnałem długości ramy.
    reach_score = _axis_score(reach_delta, neutral=14.0, severe=38.0)
    if reach_delta < -14.0:
        small_score += reach_score * 1.15
        _append_axis_reason(
            delta=reach_delta, value=bike.reach, target=target.reach, label="Reach",
            small_reasons=small_reasons, large_reasons=large_reasons,
        )
    elif reach_delta > 14.0:
        large_score += reach_score * 1.15
        _append_axis_reason(
            delta=reach_delta, value=bike.reach, target=target.reach, label="Reach",
            small_reasons=small_reasons, large_reasons=large_reasons,
        )

    stack_score = _axis_score(stack_delta, neutral=22.0, severe=55.0)
    if stack_delta < -22.0:
        small_score += stack_score
        _append_axis_reason(
            delta=stack_delta, value=bike.stack, target=target.stack, label="Stack",
            small_reasons=small_reasons, large_reasons=large_reasons,
        )
    elif stack_delta > 22.0:
        large_score += stack_score
        _append_axis_reason(
            delta=stack_delta, value=bike.stack, target=target.stack, label="Stack",
            small_reasons=small_reasons, large_reasons=large_reasons,
        )

    seat_score = _axis_score(seat_delta, neutral=24.0, severe=58.0)
    if seat_delta < -24.0:
        small_score += seat_score * 0.8
        _append_axis_reason(
            delta=seat_delta, value=bike.seat_tube_length, target=target.seat_tube,
            label="Rura podsiodłowa", small_reasons=small_reasons, large_reasons=large_reasons,
        )
    elif seat_delta > 24.0:
        large_score += seat_score * 0.8
        _append_axis_reason(
            delta=seat_delta, value=bike.seat_tube_length, target=target.seat_tube,
            label="Rura podsiodłowa", small_reasons=small_reasons, large_reasons=large_reasons,
        )

    # Korekty położenia kierownicy wyłącznie wzmacniają kierunek, który wynika
    # już z wymiarów ramy. Dzięki temu optimizer nie oznaczy poprawnej ramy jako
    # za dużej tylko dlatego, że wybrał nietypową korektę kokpitu.
    cockpit_reach = float(settings.handlebar_reach_delta)
    cockpit_stack = float(settings.handlebar_stack_delta)
    geometry_direction = "small" if small_score > large_score else "large" if large_score > small_score else "neutral"

    if geometry_direction == "small":
        if cockpit_reach > 24.0:
            small_score += min(0.7, (cockpit_reach - 20.0) / 45.0)
            small_reasons.append(
                f"Dodatkowo kokpit trzeba wydłużyć o {cockpit_reach:+.0f} mm, co potwierdza krótki zasięg ramy."
            )
        if cockpit_stack > 38.0:
            small_score += min(0.55, (cockpit_stack - 34.0) / 55.0)
            small_reasons.append(
                f"Kierownicę trzeba podnieść o {cockpit_stack:+.0f} mm, co wspiera ocenę niskiego stacku."
            )
    elif geometry_direction == "large":
        if cockpit_reach < -24.0:
            large_score += min(0.7, (-cockpit_reach - 20.0) / 45.0)
            large_reasons.append(
                f"Dodatkowo kokpit trzeba skrócić o {abs(cockpit_reach):.0f} mm, co potwierdza długi zasięg ramy."
            )
        if cockpit_stack < -38.0:
            large_score += min(0.55, (-cockpit_stack - 34.0) / 55.0)
            large_reasons.append(
                f"Kierownicę trzeba obniżyć o {abs(cockpit_stack):.0f} mm, co wspiera ocenę wysokiego stacku."
            )

    dominant = max(small_score, large_score)
    difference = abs(small_score - large_score)

    # Szeroka strefa neutralna — korekty kokpitu nie wystarczą, by ją opuścić.
    strong_named_mismatch = max(size_small, size_large) >= 2.5
    if (dominant < 1.55 or difference < 0.75) and not strong_named_mismatch:
        return FrameSizeAssessment(
            status="good",
            title="Rozmiar ramy wygląda odpowiednio",
            summary=(
                "Stack, reach i wysokość części podsiodłowej mieszczą się w orientacyjnym zakresie dla podanego wzrostu i przekroku."
            ),
            reasons=(
                f"Stack: {bike.stack:.0f} mm (punkt odniesienia około {target.stack:.0f} mm).",
                f"Reach: {bike.reach:.0f} mm (punkt odniesienia około {target.reach:.0f} mm).",
                f"Rura podsiodłowa: {bike.seat_tube_length:.0f} mm (punkt odniesienia około {target.seat_tube:.0f} mm).",
            ),
            suggestion=(
                "Pozostań przy tym rozmiarze i dopracuj pozycję położeniem siodła, mostkiem i podkładkami. "
                "Dla pewności porównaj tabelę producenta i wykonaj jazdę próbną."
            ),
            confidence="umiarkowana",
            small_score=small_score,
            large_score=large_score,
        )

    direction_small = small_score > large_score
    if dominant >= 4.0 and difference >= 1.15:
        status = "too_small" if direction_small else "too_large"
        title = "Rama jest prawdopodobnie za mała" if direction_small else "Rama jest prawdopodobnie za duża"
        summary = (
            "Kilka podstawowych wymiarów ramy jest mniejszych niż orientacyjny zakres dla tej osoby."
            if direction_small
            else "Kilka podstawowych wymiarów ramy jest większych niż orientacyjny zakres dla tej osoby."
        )
        suggestion = (
            "Sprawdź ten sam model o jeden rozmiar większy i porównaj przede wszystkim stack oraz reach."
            if direction_small
            else "Sprawdź ten sam model o jeden rozmiar mniejszy i porównaj przede wszystkim stack oraz reach."
        )
        confidence = "podwyższona"
    else:
        status = "borderline_small" if direction_small else "borderline_large"
        title = "Rama może być na granicy za małego rozmiaru" if direction_small else "Rama może być na granicy za dużego rozmiaru"
        summary = (
            "Geometria znajduje się blisko granicy orientacyjnego zakresu; sąsiedni rozmiar warto porównać przed ostateczną decyzją."
        )
        suggestion = (
            "Porównaj geometrię z następnym większym rozmiarem. Wybierz ten, który wymaga mniejszych korekt stacku i reachu."
            if direction_small
            else "Porównaj geometrię z następnym mniejszym rozmiarem. Wybierz ten, który wymaga mniejszych korekt stacku i reachu."
        )
        confidence = "umiarkowana"

    reasons = tuple((small_reasons if direction_small else large_reasons)[:5])
    return FrameSizeAssessment(
        status=status,
        title=title,
        summary=summary,
        reasons=reasons,
        suggestion=suggestion,
        confidence=confidence,
        small_score=small_score,
        large_score=large_score,
    )
