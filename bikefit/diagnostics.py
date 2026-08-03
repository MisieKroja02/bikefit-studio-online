from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .kinematics import CycleAnalysis, style_targets
from .models import BikeGeometry, FitSettings, Rider
from .recommendations import base_recommendation


@dataclass(frozen=True)
class FitDiagnostic:
    severity: str
    area: str
    title: str
    measured: str
    why: str
    possible_effect: str
    correction: str
    priority: int


def _mm_step(delta: float, minimum: int = 3, maximum: int = 20) -> int:
    return int(round(max(minimum, min(maximum, abs(delta)))))


def explain_fit(
    bike: BikeGeometry,
    rider: Rider,
    settings: FitSettings,
    analysis: CycleAnalysis,
    threshold: float = 90.0,
) -> List[FitDiagnostic]:
    """Wyjaśnia, dlaczego bieżące ustawienie traci punkty modelu.

    Diagnostyka jest orientacyjna. Łączy rzeczywiste kąty wyliczone dla pełnego
    obrotu korby z różnicą względem ustawienia bazowego dla proporcji użytkownika.
    """
    if analysis.score >= threshold:
        return []

    reference = base_recommendation(rider, bike, settings.style, rider.flexibility).settings
    targets = style_targets(settings.style)
    items: List[FitDiagnostic] = []
    used_areas: set[str] = set()

    def add(item: FitDiagnostic) -> None:
        if item.area not in used_areas:
            items.append(item)
            used_areas.add(item.area)

    if analysis.unreachable_samples:
        add(FitDiagnostic(
            severity="critical",
            area="Zasięg nogi",
            title="Noga nie osiąga poprawnej pozycji w części obrotu",
            measured=f"Brak rozwiązania dla {analysis.unreachable_samples}/72 pozycji korby",
            why="Odległość biodro–pedał jest większa niż pozwala na to długość uda i podudzia w modelu. Najczęściej oznacza to zbyt wysokie lub zbyt cofnięte siodło.",
            possible_effect="Na realnym rowerze może pojawić się kołysanie bioder, wyciąganie palców do pedału i nierówny nacisk na pedały.",
            correction="Obniż siodło o 5 mm i sprawdź ponownie. Jeśli problem pozostaje, przesuń siodło 3–5 mm do przodu.",
            priority=100,
        ))

    if analysis.knee_flexion_min < 25.0:
        delta = settings.saddle_height - reference.saddle_height
        step = _mm_step(delta if delta > 0 else 5.0)
        add(FitDiagnostic(
            severity="critical" if analysis.knee_flexion_min < 20.0 else "warning",
            area="Wysokość siodła",
            title="Siodło jest prawdopodobnie za wysoko",
            measured=f"Minimalne zgięcie kolana {analysis.knee_flexion_min:.1f}°; zakres startowy 25–35°",
            why="Przy dolnym położeniu korby noga prostuje się bardziej niż przyjęty zakres. Biodro musi wtedy szukać dodatkowego zasięgu albo stopa zaczyna mocniej pracować palcami w dół.",
            possible_effect="Może to zwiększać napięcie tylnej części uda i łydki oraz powodować kołysanie miednicy i dyskomfort z tyłu kolana.",
            correction=f"Obniż siodło orientacyjnie o {step} mm, a następnie testuj zmianę po 2–3 mm.",
            priority=95,
        ))
    elif analysis.knee_flexion_min > 35.0:
        delta = reference.saddle_height - settings.saddle_height
        step = _mm_step(delta if delta > 0 else 5.0)
        add(FitDiagnostic(
            severity="critical" if analysis.knee_flexion_min > 42.0 else "warning",
            area="Wysokość siodła",
            title="Siodło jest prawdopodobnie za nisko",
            measured=f"Minimalne zgięcie kolana {analysis.knee_flexion_min:.1f}°; zakres startowy 25–35°",
            why="Kolano pozostaje zbyt mocno zgięte nawet przy najdalszym położeniu pedału. Noga nie ma miejsca na efektywne wyprostowanie w fazie nacisku.",
            possible_effect="Może wzrosnąć obciążenie przedniej części kolana i mięśnia czworogłowego, a pedałowanie może wydawać się ciężkie i ciasne.",
            correction=f"Podnieś siodło orientacyjnie o {step} mm, wprowadzając zmianę stopniowo po 2–3 mm.",
            priority=95,
        ))

    if analysis.knee_flexion_max > 125.0:
        add(FitDiagnostic(
            severity="warning",
            area="Zgięcie kolana u góry",
            title="Kolano jest nadmiernie zgięte w górnej części obrotu",
            measured=f"Maksymalne zgięcie {analysis.knee_flexion_max:.1f}°; zakres modelu 98–125°",
            why="Przy górnym położeniu korby udo i podudzie zbliżają się do siebie zbyt mocno. Przyczyną może być zbyt niskie siodło, zbyt długa korba albo siodło wysunięte za bardzo do przodu.",
            possible_effect="Może to powodować uczucie ścisku w biodrze i kolanie oraz utrudniać płynne przejście przez górę obrotu.",
            correction="Najpierw sprawdź wysokość siodła. Jeśli jest prawidłowa, cofnij siodło 3–5 mm lub rozważ krótszą korbę.",
            priority=85,
        ))
    elif analysis.knee_flexion_max < 98.0:
        add(FitDiagnostic(
            severity="warning",
            area="Zgięcie kolana u góry",
            title="Noga pozostaje zbyt wyprostowana również u góry obrotu",
            measured=f"Maksymalne zgięcie {analysis.knee_flexion_max:.1f}°; zakres modelu 98–125°",
            why="Cały cykl pracy nogi jest przesunięty w stronę nadmiernego wyprostu. Najczęściej siodło jest za wysoko albo za daleko do tyłu.",
            possible_effect="Może to ograniczać kontrolę nad pedałem i zwiększać napięcie tylnej taśmy mięśniowej.",
            correction="Obniż siodło o 3–5 mm lub przesuń je nieznacznie do przodu, a następnie ponownie sprawdź zakres kolana.",
            priority=82,
        ))

    if analysis.hip_angle_min < targets["hip_min"]:
        stack_low = settings.handlebar_stack_delta < reference.handlebar_stack_delta - 6.0
        reach_long = settings.handlebar_reach_delta > reference.handlebar_reach_delta + 6.0
        saddle_forward = settings.saddle_fore_aft > reference.saddle_fore_aft + 6.0
        likely = []
        if stack_low:
            likely.append("kierownica jest za nisko")
        if reach_long:
            likely.append("zasięg do kierownicy jest za długi")
        if saddle_forward:
            likely.append("siodło jest zbyt wysunięte do przodu")
        cause = ", ".join(likely) if likely else "kokpit jest zbyt niski lub zbyt długi dla aktualnej mobilności"
        add(FitDiagnostic(
            severity="critical" if analysis.hip_angle_min < targets["hip_min"] - 8.0 else "warning",
            area="Otwarcie biodra",
            title="Biodro jest zbyt mocno zamknięte",
            measured=f"Minimalny kąt biodra {analysis.hip_angle_min:.1f}°; minimum dla profilu {targets['hip_min']:.0f}°",
            why=f"W górnej części obrotu brzuch i udo zbliżają się zbyt mocno. Najbardziej prawdopodobna przyczyna: {cause}.",
            possible_effect="Może to utrudniać swobodny oddech, powodować kołysanie kolan na boki i zwiększać napięcie w pachwinie lub dolnych plecach.",
            correction="Podnieś kierownicę o 5–10 mm albo skróć zasięg o 5–10 mm. Zmieniaj tylko jeden parametr naraz.",
            priority=90,
        ))

    if analysis.elbow_angle > 168.0:
        delta = settings.handlebar_reach_delta - reference.handlebar_reach_delta
        step = _mm_step(delta if delta > 0 else 8.0, 5, 15)
        add(FitDiagnostic(
            severity="warning",
            area="Zasięg kierownicy",
            title="Kokpit jest prawdopodobnie za długi",
            measured=f"Kąt łokcia {analysis.elbow_angle:.1f}°; zalecany zakres modelu 142–168°",
            why="Ręce są niemal wyprostowane, więc tułów musi sięgać do chwytu zamiast opierać się na lekko ugiętych łokciach.",
            possible_effect="Może wzrosnąć nacisk na dłonie, napięcie karku i barków oraz trudność w amortyzowaniu nierówności rękami.",
            correction=f"Skróć zasięg do kierownicy orientacyjnie o {step} mm lub zastosuj krótszy mostek.",
            priority=88,
        ))
    elif 0.0 < analysis.elbow_angle < 142.0:
        delta = reference.handlebar_reach_delta - settings.handlebar_reach_delta
        step = _mm_step(delta if delta > 0 else 8.0, 5, 15)
        add(FitDiagnostic(
            severity="warning",
            area="Zasięg kierownicy",
            title="Kokpit jest prawdopodobnie za krótki",
            measured=f"Kąt łokcia {analysis.elbow_angle:.1f}°; zalecany zakres modelu 142–168°",
            why="Łokcie są mocno zgięte, a barki mogą pozostawać cofnięte. Pozycja staje się ciasna i ogranicza swobodę ruchu tułowia.",
            possible_effect="Może pojawić się przeciążenie tricepsów, uczucie ścisku między kolanami i kierownicą oraz niestabilne prowadzenie.",
            correction=f"Wydłuż zasięg do chwytu orientacyjnie o {step} mm, np. dłuższym mostkiem lub ustawieniem klamek.",
            priority=88,
        ))

    target_torso = targets["torso"]
    if analysis.torso_angle < target_torso - 10.0:
        add(FitDiagnostic(
            severity="warning",
            area="Pochylenie tułowia",
            title="Tułów jest zbyt nisko względem wybranego profilu",
            measured=f"Pochylenie {analysis.torso_angle:.1f}°; cel profilu około {target_torso:.0f}°",
            why="Kierownica znajduje się za nisko lub za daleko, przez co pozycja jest bardziej agresywna niż wybrany charakter jazdy i mobilność użytkownika.",
            possible_effect="Może zwiększyć napięcie karku, barków i odcinka lędźwiowego oraz nacisk na dłonie.",
            correction="Podnieś kierownicę o 5–10 mm lub skróć zasięg o 5 mm.",
            priority=75,
        ))
    elif analysis.torso_angle > target_torso + 10.0:
        add(FitDiagnostic(
            severity="warning",
            area="Pochylenie tułowia",
            title="Tułów jest zbyt pionowo względem wybranego profilu",
            measured=f"Pochylenie {analysis.torso_angle:.1f}°; cel profilu około {target_torso:.0f}°",
            why="Kierownica jest bardzo wysoko lub blisko. Pozycja może być wygodna chwilowo, ale odbiega od wybranego profilu i przenosi dużą część masy na siodło.",
            possible_effect="Może zmniejszyć stabilność przodu na podjazdach, zwiększyć nacisk na siodło i pogorszyć aerodynamikę.",
            correction="Obniż kierownicę o 5 mm lub wydłuż zasięg o 5 mm, jeśli nie pojawia się ból ani drętwienie.",
            priority=70,
        ))

    fore_aft_delta = settings.saddle_fore_aft - reference.saddle_fore_aft
    if abs(fore_aft_delta) > 10.0 and "Otwarcie biodra" not in used_areas:
        if fore_aft_delta > 0:
            add(FitDiagnostic(
                severity="warning",
                area="Przesunięcie siodła",
                title="Siodło jest wyraźnie bardziej z przodu niż punkt bazowy",
                measured=f"Różnica względem ustawienia bazowego: +{fore_aft_delta:.0f} mm do przodu",
                why="Przesunięcie bioder do przodu zmniejsza przestrzeń między udem a tułowiem i zwiększa udział kolana w generowaniu siły.",
                possible_effect="Może zwiększyć nacisk na dłonie i przednią część kolana oraz ograniczyć pracę pośladków.",
                correction=f"Cofnij siodło o około {_mm_step(fore_aft_delta, 5, 15)} mm i sprawdź ponownie kąty.",
                priority=72,
            ))
        else:
            add(FitDiagnostic(
                severity="warning",
                area="Przesunięcie siodła",
                title="Siodło jest wyraźnie bardziej cofnięte niż punkt bazowy",
                measured=f"Różnica względem ustawienia bazowego: {fore_aft_delta:.0f} mm",
                why="Cofnięcie bioder wydłuża efektywny zasięg do kierownicy i zwiększa odległość do pedału w przedniej części obrotu.",
                possible_effect="Może zwiększyć napięcie tylnej części uda, wymuszać sięganie do kierownicy i kołysanie bioder.",
                correction=f"Przesuń siodło do przodu o około {_mm_step(fore_aft_delta, 5, 15)} mm.",
                priority=72,
            ))

    # Gdy wynik jest poniżej progu, ale kąty nie przekroczyły twardych granic,
    # pokaż największe odchylenie od ustawienia bazowego zamiast pustego komunikatu.
    if not items:
        deviations = [
            (abs(settings.saddle_height - reference.saddle_height), "Wysokość siodła", settings.saddle_height - reference.saddle_height),
            (abs(settings.saddle_fore_aft - reference.saddle_fore_aft), "Przesunięcie siodła", settings.saddle_fore_aft - reference.saddle_fore_aft),
            (abs(settings.handlebar_stack_delta - reference.handlebar_stack_delta), "Wysokość kierownicy", settings.handlebar_stack_delta - reference.handlebar_stack_delta),
            (abs(settings.handlebar_reach_delta - reference.handlebar_reach_delta), "Zasięg kierownicy", settings.handlebar_reach_delta - reference.handlebar_reach_delta),
        ]
        _, area, delta = max(deviations, key=lambda row: row[0])
        direction = "więcej" if delta > 0 else "mniej"
        add(FitDiagnostic(
            severity="warning",
            area=area,
            title="Ustawienie odbiega od punktu bazowego proporcji ciała",
            measured=f"Odchylenie {delta:+.0f} mm względem wartości bazowej",
            why=f"Największa różnica dotyczy parametru „{area}”. Model ocenia łączny wpływ kilku mniejszych odchyleń, nawet gdy pojedynczy kąt nie przekracza twardej granicy.",
            possible_effect="Pozycja może być mniej stabilna lub szybciej powodować zmęczenie podczas dłuższej jazdy.",
            correction=f"Przywróć ten parametr bliżej ustawienia bazowego — zastosuj {direction} korekty w krokach po 3–5 mm.",
            priority=60,
        ))

    items.sort(key=lambda item: item.priority, reverse=True)
    return items[:5]
