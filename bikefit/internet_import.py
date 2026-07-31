from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, Tuple

from .models import BikeGeometry


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() in {"br", "p", "div", "tr", "td", "th", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)
            if self._in_title:
                self.title += clean + " "

    def text(self) -> str:
        return " ".join(self.parts)


ALIASES: Dict[str, tuple[str, ...]] = {
    "stack": ("stack",),
    "reach": ("reach",),
    "seat_tube_angle": ("seat tube angle", "kąt rury podsiodłowej", "seat angle"),
    "head_tube_angle": ("head tube angle", "kąt główki ramy", "head angle"),
    "head_tube_length": ("head tube length", "długość główki ramy", "head tube"),
    "seat_tube_length": ("seat tube length", "długość rury podsiodłowej", "seat tube"),
    "top_tube": ("top tube length", "effective top tube", "top tube", "górna rura"),
    "bb_drop": ("bottom bracket drop", "bb drop", "obniżenie suportu"),
    "chainstay": ("chainstay length", "chainstay", "długość dolnych widełek"),
    "wheelbase": ("wheelbase", "rozstaw osi"),
    "fork_offset": ("fork offset", "fork rake", "offset widelca"),
    "stem_length": ("stem length", "długość mostka", "stem"),
    "crank_length": ("crank length", "długość korby", "crank"),
}

ANGLE_FIELDS = {"seat_tube_angle", "head_tube_angle"}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", value.replace("\u00a0", " "))
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def _flatten_json(payload: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            full = f"{prefix} {key}".strip().lower().replace("_", "-")
            yield full, value
            yield from _flatten_json(value, full)
    elif isinstance(payload, list):
        for value in payload:
            yield from _flatten_json(value, prefix)


def _extract_from_json(payload: Any) -> Dict[str, float]:
    result: Dict[str, float] = {}
    flat = list(_flatten_json(payload))
    for field, aliases in ALIASES.items():
        for key, value in flat:
            normalized = key.replace("-", " ")
            if field.endswith("_angle") and "angle" not in normalized and "kąt" not in normalized:
                continue
            if field in {"head_tube_length", "seat_tube_length", "stem_length", "crank_length"} and ("angle" in normalized or "kąt" in normalized):
                continue
            if any(alias in normalized for alias in aliases):
                number = _number(value)
                if number is not None:
                    result[field] = number
                    break
    return result


def _extract_from_text(text: str) -> Dict[str, float]:
    normalized = re.sub(r"\s+", " ", text).lower()
    result: Dict[str, float] = {}
    for field, aliases in ALIASES.items():
        unit = r"(?:mm|cm|°|deg|degrees?)?"
        for alias in aliases:
            pattern = rf"{re.escape(alias)}\s*(?:\([^)]*\))?\s*[:|=\-–—.]?\s*(-?\d+(?:[.,]\d+)?)\s*{unit}"
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                value = float(match.group(1).replace(",", "."))
                # Konwersja cm -> mm tylko dla wymiarów liniowych, gdy jednostka jest jawna.
                tail = normalized[match.end(1): match.end(1) + 5]
                if field not in ANGLE_FIELDS and re.match(r"\s*cm", tail):
                    value *= 10.0
                result[field] = value
                break
    return result


def fetch_geometry(url: str, base: BikeGeometry | None = None) -> tuple[BikeGeometry, list[str]]:
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Adres musi zaczynać się od http:// lub https://")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 BikeFitSimulator/1.0",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(3_000_000)
            content_type = response.headers.get("Content-Type", "")
            encoding = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Serwer zwrócił błąd HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Nie udało się połączyć ze stroną: {exc.reason}") from exc

    text = raw.decode(encoding, errors="replace")
    title = "Rower pobrany z internetu"
    extracted: Dict[str, float] = {}

    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        try:
            payload = json.loads(text)
            extracted.update(_extract_from_json(payload))
            if isinstance(payload, dict):
                title = str(payload.get("name") or payload.get("title") or title)
        except json.JSONDecodeError:
            pass
    else:
        parser = _TextExtractor()
        parser.feed(text)
        title = parser.title.strip() or title
        extracted.update(_extract_from_text(parser.text()))
        # Wiele stron przechowuje geometrię również w JSON osadzonym w skrypcie.
        for match in re.finditer(r"<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>(.*?)</script>", text, re.I | re.S):
            try:
                extracted.update(_extract_from_json(json.loads(match.group(1))))
            except (json.JSONDecodeError, TypeError):
                continue

    geometry = BikeGeometry.from_dict((base or BikeGeometry()).to_dict())
    geometry.name = title[:120]
    for key, value in extracted.items():
        setattr(geometry, key, value)

    required = ("stack", "reach", "seat_tube_angle", "head_tube_angle", "wheelbase", "chainstay", "bb_drop")
    missing = [field for field in required if field not in extracted]
    notes = [f"Rozpoznano {len(extracted)} parametrów: {', '.join(sorted(extracted)) or 'brak' }."]
    if missing:
        notes.append("Nie rozpoznano: " + ", ".join(missing) + ". Pozostawiono wcześniejsze wartości.")
    notes.append("Importer jest heurystyczny — po pobraniu porównaj liczby z tabelą producenta.")
    return geometry, notes
