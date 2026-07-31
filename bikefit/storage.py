from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .models import BikeGeometry, FitSettings, Rider


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
BIKES_FILE = DATA_DIR / "bikes.json"


def load_bikes() -> List[BikeGeometry]:
    try:
        payload = json.loads(BIKES_FILE.read_text(encoding="utf-8"))
        return [BikeGeometry.from_dict(item) for item in payload]
    except (OSError, json.JSONDecodeError, TypeError):
        return [BikeGeometry()]


def save_bikes(bikes: List[BikeGeometry]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BIKES_FILE.write_text(
        json.dumps([bike.to_dict() for bike in bikes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_profile(path: str, bike: BikeGeometry, rider: Rider, settings: FitSettings) -> None:
    payload = {
        "bike": bike.to_dict(),
        "rider": rider.to_dict(),
        "settings": settings.to_dict(),
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: str) -> tuple[BikeGeometry, Rider, FitSettings]:
    payload: Dict[str, object] = json.loads(Path(path).read_text(encoding="utf-8"))
    return (
        BikeGeometry.from_dict(payload.get("bike", {})),
        Rider.from_dict(payload.get("rider", {})),
        FitSettings.from_dict(payload.get("settings", {})),
    )
