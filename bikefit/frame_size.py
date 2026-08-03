from __future__ import annotations

from dataclasses import dataclass

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


def _positive(value: float) -> float:
    return max(0.0, float(value))


def _cockpit_limits(bike_type: str) -> tuple[float, float, float, float]:
    """Zwraca orientacyjne granice korekt: reach+, reach-, stack+, stack-."""
    kind = (bike_type or "").lower()
    if kind in {"mtb", "mountain"}:
        return 30.0, 30.0, 40.0, 40.0
    if kind in {"trekking", "city", "urban"}:
        return 25.0, 25.0, 35.0, 35.0
    return 22.0, 22.0, 32.0, 32.0


def assess_frame_size(
    bike: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
) -> FrameSizeAssessment:
    """Orientacyjnie ocenia rozmiar ramy na podstawie geometrii i wymaganych korekt.

    Najsilniejszym sygnałem są duże korekty wysokości i zasięgu kierownicy.
    Dodatkowo uwzględniana jest ekspozycja sztycy oraz relacja stack/reach do wzrostu.
    Wynik nie zastępuje tabeli producenta ani jazdy próbnej.
    """

    reach_pos_limit, reach_neg_limit, stack_pos_limit, stack_neg_limit = _cockpit_limits(bike.bike_type)
    small_score = 0.0
    large_score = 0.0
    small_reasons: list[str] = []
    large_reasons: list[str] = []

    reach_delta = float(settings.handlebar_reach_delta)
    stack_delta = float(settings.handlebar_stack_delta)

    if reach_delta > reach_pos_limit:
        strength = 1.5 + _positive(reach_delta - reach_pos_limit) / 18.0
        small_score += strength
        small_reasons.append(
            f"Aby uzyskać właściwy zasięg, program wydłuża kokpit o {reach_delta:+.0f} mm. "
            "Duża dodatnia korekta często oznacza zbyt krótką ramę."
        )
    elif reach_delta < -reach_neg_limit:
        strength = 1.5 + _positive(-reach_delta - reach_neg_limit) / 18.0
        large_score += strength
        large_reasons.append(
            f"Aby uzyskać właściwy zasięg, program skraca kokpit o {reach_delta:+.0f} mm. "
            "Duża ujemna korekta często oznacza zbyt długą ramę."
        )

    if stack_delta > stack_pos_limit:
        strength = 1.2 + _positive(stack_delta - stack_pos_limit) / 22.0
        small_score += strength
        small_reasons.append(
            f"Kierownicę trzeba podnieść o {stack_delta:+.0f} mm. Rama może mieć za niski stack dla tej osoby i wybranego stylu."
        )
    elif stack_delta < -stack_neg_limit:
        strength = 1.2 + _positive(-stack_delta - stack_neg_limit) / 22.0
        large_score += strength
        large_reasons.append(
            f"Kierownicę trzeba obniżyć o {stack_delta:+.0f} mm. Rama może mieć za wysoki stack."
        )

    # Orientacyjna ekspozycja sztycy: wysokość siodła minus długość rury podsiodłowej.
    # To sygnał pomocniczy, bo nowoczesne ramy mogą mieć mocno opadającą rurę górną.
    seatpost_exposure = float(settings.saddle_height) - float(bike.seat_tube_length)
    if seatpost_exposure > 255.0:
        small_score += min(1.2, (seatpost_exposure - 235.0) / 55.0)
        small_reasons.append(
            f"Orientacyjna ekspozycja sztycy wynosi około {seatpost_exposure:.0f} mm. "
            "Bardzo duża wartość może wskazywać na małą ramę, choć zależy od konstrukcji ramy."
        )
    elif seatpost_exposure < 105.0:
        large_score += min(1.2, (125.0 - seatpost_exposure) / 45.0)
        large_reasons.append(
            f"Orientacyjna ekspozycja sztycy wynosi tylko około {seatpost_exposure:.0f} mm. "
            "Mały zapas może wskazywać na dużą ramę lub ograniczoną możliwość obniżenia siodła."
        )

    # Niezależny, słabszy sygnał proporcji samej ramy do wzrostu.
    height = max(1.0, float(rider.height))
    stack_ratio = float(bike.stack) / height
    reach_ratio = float(bike.reach) / height
    kind = (bike.bike_type or "").lower()
    if kind in {"mtb", "mountain"}:
        stack_low, stack_high = 0.325, 0.375
        reach_low, reach_high = 0.225, 0.270
    elif kind in {"trekking", "city", "urban"}:
        stack_low, stack_high = 0.325, 0.375
        reach_low, reach_high = 0.195, 0.235
    else:
        stack_low, stack_high = 0.295, 0.345
        reach_low, reach_high = 0.195, 0.235

    if reach_ratio < reach_low - 0.008:
        small_score += 0.7
        small_reasons.append(
            f"Reach ramy ({bike.reach:.0f} mm) jest krótki względem wzrostu {rider.height:.0f} mm."
        )
    elif reach_ratio > reach_high + 0.008:
        large_score += 0.7
        large_reasons.append(
            f"Reach ramy ({bike.reach:.0f} mm) jest długi względem wzrostu {rider.height:.0f} mm."
        )

    if stack_ratio < stack_low - 0.010:
        small_score += 0.5
        small_reasons.append(
            f"Stack ramy ({bike.stack:.0f} mm) jest niski względem wzrostu i może wymagać wielu podkładek."
        )
    elif stack_ratio > stack_high + 0.010:
        large_score += 0.5
        large_reasons.append(
            f"Stack ramy ({bike.stack:.0f} mm) jest wysoki względem wzrostu i może ograniczać możliwość obniżenia kierownicy."
        )

    dominant = max(small_score, large_score)
    difference = abs(small_score - large_score)

    if dominant < 1.35 or difference < 0.55:
        return FrameSizeAssessment(
            status="good",
            title="Rozmiar ramy wygląda odpowiednio",
            summary=(
                "Wymagane korekty kokpitu mieszczą się w rozsądnym zakresie. Nie ma wyraźnego sygnału, "
                "że rama jest za mała lub za duża."
            ),
            reasons=(
                f"Korekta wysokości kierownicy: {stack_delta:+.0f} mm; korekta zasięgu: {reach_delta:+.0f} mm.",
                f"Orientacyjna ekspozycja sztycy: {seatpost_exposure:.0f} mm.",
            ),
            suggestion=(
                "Pozostań przy tym rozmiarze i dopracuj ustawienie mostkiem, podkładkami oraz położeniem siodła. "
                "Dla pewności porównaj też tabelę producenta i wykonaj jazdę próbną."
            ),
            confidence="umiarkowana",
            small_score=small_score,
            large_score=large_score,
        )

    direction_small = small_score > large_score
    if dominant >= 3.0 and difference >= 1.0:
        status = "too_small" if direction_small else "too_large"
        title = "Rama jest prawdopodobnie za mała" if direction_small else "Rama jest prawdopodobnie za duża"
        summary = (
            "Aby osiągnąć docelową pozycję, potrzebne są duże korekty w kierunku wydłużenia lub podniesienia kokpitu."
            if direction_small
            else "Aby osiągnąć docelową pozycję, potrzebne są duże korekty w kierunku skrócenia lub obniżenia kokpitu."
        )
        suggestion = (
            "Sprawdź ten sam model o jeden rozmiar większy. Porównaj przede wszystkim stack i reach; większa rama zwykle zwiększa oba wymiary."
            if direction_small
            else "Sprawdź ten sam model o jeden rozmiar mniejszy. Szukaj mniejszego reachu i niższego stacku, aby ograniczyć skrajne korekty."
        )
        confidence = "podwyższona"
    else:
        status = "borderline_small" if direction_small else "borderline_large"
        title = "Rama może być na granicy za małego rozmiaru" if direction_small else "Rama może być na granicy za dużego rozmiaru"
        summary = (
            "Pozycję da się ustawić, ale wymaga ona korekt zbliżających się do praktycznych granic regulacji."
        )
        suggestion = (
            "Porównaj geometrię z następnym większym rozmiarem. Jeśli wymaga on mniejszych korekt reachu i stacku, może być lepszym punktem wyjścia."
            if direction_small
            else "Porównaj geometrię z następnym mniejszym rozmiarem. Jeśli ograniczy potrzebę krótkiego mostka i dużego obniżenia kierownicy, może być lepszy."
        )
        confidence = "umiarkowana"

    reasons = tuple((small_reasons if direction_small else large_reasons)[:4])
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
