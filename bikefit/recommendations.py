from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List

from .kinematics import analyze_cycle, bike_points
from .models import BikeGeometry, FitSettings, Rider


FLEX_VALUES = {
    "Ograniczona": 0,
    "Średnia": 1,
    "Dobra": 2,
}


@dataclass
class FitRecommendation:
    settings: FitSettings
    notes: List[str]


def estimate_saddle_height(rider: Rider, bike: BikeGeometry, style: str) -> float:
    # Klasyczny punkt startowy z korektą pod długość korby i styl pozycji.
    base = rider.inseam * 0.883
    crank_delta = bike.crank_length - 172.5
    base -= 0.25 * crank_delta
    if style == "Komfortowa":
        base -= 2.0
    elif style == "Sportowa":
        base += 2.0
    return base


def estimate_fore_aft(rider: Rider, style: str) -> float:
    thigh_ratio = rider.thigh / max(1.0, rider.shank)
    base = (thigh_ratio - 1.08) * 45.0
    if style == "Komfortowa":
        base += 2.0
    elif style == "Sportowa":
        base -= 3.0
    return max(-35.0, min(30.0, base))


def estimate_cockpit(rider: Rider, bike: BikeGeometry, style: str, flexibility: str) -> tuple[float, float]:
    flex = FLEX_VALUES.get(flexibility, 1)
    arm_torso = rider.torso + rider.upper_arm + rider.forearm
    reference = rider.height * 0.61
    length_bias = (arm_torso - reference) * 0.12
    reach = length_bias
    stack = 0.0
    if style == "Komfortowa":
        stack += 25.0
        reach -= 8.0
    elif style == "Sportowa":
        stack -= 10.0
        reach += 8.0
    # Mobilność: większa ruchomość pozwala zejść niżej i sięgnąć dalej.
    stack += {0: 20.0, 1: 5.0, 2: -8.0}[flex]
    reach += {0: -10.0, 1: 0.0, 2: 8.0}[flex]
    return max(-50.0, min(80.0, stack)), max(-60.0, min(60.0, reach))


def base_recommendation(rider: Rider, bike: BikeGeometry, style: str, flexibility: str) -> FitRecommendation:
    saddle_height = estimate_saddle_height(rider, bike, style)
    saddle_fore_aft = estimate_fore_aft(rider, style)
    stack_delta, reach_delta = estimate_cockpit(rider, bike, style, flexibility)
    cadence = 80.0 if style == "Komfortowa" else 88.0 if style == "Zrównoważona" else 92.0
    foot_angle = -7.0
    settings = FitSettings(
        saddle_height=saddle_height,
        saddle_fore_aft=saddle_fore_aft,
        handlebar_stack_delta=stack_delta,
        handlebar_reach_delta=reach_delta,
        cadence=cadence,
        foot_angle=foot_angle,
        style=style,
    )
    points = bike_points(bike, settings)
    saddle_to_bar_reach = points["hand"][0] - points["saddle"][0]
    saddle_to_bar_drop = points["saddle"][1] - points["hand"][1]
    notes = [
        "Bazowy dobór wykorzystuje proporcje ciała, wzór 0,883 dla wysokości siodła oraz korekty zależne od stylu jazdy i mobilności.",
        f"Startowa wysokość siodła: {saddle_height:.0f} mm od środka suportu do górnej powierzchni siodła.",
        f"Startowe przesunięcie siodła: {saddle_fore_aft:+.0f} mm względem pozycji neutralnej modelu.",
        f"Orientacyjny cockpit: reach {saddle_to_bar_reach:.0f} mm, drop {saddle_to_bar_drop:.0f} mm między siodłem i dłońmi.",
        "Potem warto zweryfikować to na spokojnej jeździe testowej oraz według odczuć bioder, kolan, karku i dłoni.",
    ]
    return FitRecommendation(settings=settings, notes=notes)


def measurement_guide(bike: BikeGeometry, settings: FitSettings) -> List[str]:
    points = bike_points(bike, settings)
    saddle_to_bar_reach = points["hand"][0] - points["saddle"][0]
    saddle_to_bar_drop = points["saddle"][1] - points["hand"][1]
    setback = max(0.0, -points["saddle"][0])
    return [
        "M1. Wysokość siodła: przyłóż początek metrówki dokładnie do środka osi suportu i prowadź metrówkę po osi rury podsiodłowej oraz sztycy do górnej powierzchni siodła.",
        f"M1 = {settings.saddle_height:.0f} mm po linii ramy i sztycy.",
        "M2. Setback S75: znajdź środek siodła w przekroju o szerokości 75 mm. Opuść z tego punktu pion i zmierz poziomą odległość do pionu przechodzącego przez środek suportu.",
        f"M2 = {setback:.0f} mm za pionem suportu. Regulacja siodła na szynach w modelu: {settings.saddle_fore_aft:+.0f} mm.",
        "M3. Drop siodło–kierownica: zmierz pionową różnicę wysokości między punktem S75 a punktem chwytu na klamkomanetkach lub kierownicy.",
        f"M3 = {saddle_to_bar_drop:.0f} mm.",
        "M4. Reach siodło–kierownica: zmierz poziomą odległość od punktu S75 do punktu chwytu dłoni.",
        f"M4 = {saddle_to_bar_reach:.0f} mm.",
        "M5. Długość korby: od środka osi suportu do środka osi pedału.",
        f"M5 = {bike.crank_length:.1f} mm.",
        "Bloki SPD: środek osi pedału ustaw jako punkt startowy lekko za głową I kości śródstopia; zmiany wprowadzaj małymi krokami.",
    ]


def advanced_notes(style: str, flexibility: str) -> List[str]:
    notes = [
        "Model łączy praktyczne zasady fitterów z prostym modelem biomechanicznym 2D: zakres wyprostu kolana, otwarcie biodra, kąt łokcia i pochylenie tułowia.",
        "Jako start przyjmuje się najczęściej około 25–35° zgięcia kolana przy dolnym położeniu korby, a nie jedną magiczną liczbę.",
        "Wygodna pozycja zwykle wymaga lekkiego ugięcia łokci i braku nadmiernego zamknięcia biodra.",
    ]
    if style == "Komfortowa":
        notes.append("Profil komfortowy preferuje wyższą kierownicę, mniejszy zasięg i bardziej otwarte biodro.")
    elif style == "Sportowa":
        notes.append("Profil sportowy pozwala na niższą kierownicę i dłuższy zasięg, ale tylko jeśli ruchomość i brak bólu na to pozwalają.")
    if flexibility == "Ograniczona":
        notes.append("Przy ograniczonej mobilności lepiej zaczynać od wyższej kierownicy i mniejszego zasięgu.")
    elif flexibility == "Dobra":
        notes.append("Przy dobrej mobilności można bezpieczniej testować większy drop i nieco dłuższy reach.")
    return notes


def recommend_and_evaluate(rider: Rider, bike: BikeGeometry, style: str, flexibility: str) -> FitRecommendation:
    rec = base_recommendation(rider, bike, style, flexibility)
    analysis = analyze_cycle(bike, rider, rec.settings, samples=72)
    notes = list(rec.notes)
    notes.append(f"Ocena bazowego ustawienia według modelu: {analysis.score:.1f}/100.")
    notes.extend(advanced_notes(style, flexibility))
    return FitRecommendation(settings=rec.settings, notes=notes)
