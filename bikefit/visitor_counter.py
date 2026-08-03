from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


class CounterError(RuntimeError):
    pass


def counter_value(payload: object) -> int | None:
    if isinstance(payload, bool):
        return None
    if isinstance(payload, (int, float)):
        return int(payload)
    if isinstance(payload, str):
        try:
            return int(float(payload.strip()))
        except (TypeError, ValueError):
            return None
    if isinstance(payload, dict):
        for key in ("count", "value", "up_count", "total", "result"):
            if key in payload:
                parsed = counter_value(payload[key])
                if parsed is not None:
                    return parsed
        if "data" in payload:
            return counter_value(payload["data"])
    return None


def request_counter(
    api_base: str,
    namespace: str,
    name: str,
    increment: bool,
    *,
    timeout: float = 2.5,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> int:
    suffix = "/up" if increment else ""
    url = (
        f"{api_base.rstrip('/')}/{urllib.parse.quote(namespace, safe='')}/"
        f"{urllib.parse.quote(name, safe='')}{suffix}"
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "BikeFit-Studio-Online"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CounterError("Licznik jest chwilowo niedostępny.") from exc
    try:
        value = counter_value(json.loads(raw.decode("utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CounterError("Licznik zwrócił nieprawidłową odpowiedź.") from exc
    if value is None:
        raise CounterError("Licznik zwrócił nieznany format.")
    return value
