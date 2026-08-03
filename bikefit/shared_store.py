from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


class SharedStoreError(RuntimeError):
    """Błąd wspólnej bazy geometrii."""


@dataclass(frozen=True)
class GeometryStoreConfig:
    token: str
    owner: str
    repo: str
    branch: str = "main"
    path: str = "data/community_bikes.json"

    @property
    def configured(self) -> bool:
        return bool(self.token.strip() and self.owner.strip() and self.repo.strip())


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, bytes]]


def config_from_mapping(mapping: Mapping[str, Any] | None) -> GeometryStoreConfig | None:
    if not mapping:
        return None
    token = str(mapping.get("token", "")).strip()
    owner = str(mapping.get("owner", "")).strip()
    repo = str(mapping.get("repo", "")).strip()
    branch = str(mapping.get("branch", "main")).strip() or "main"
    path = str(mapping.get("path", "data/community_bikes.json")).strip() or "data/community_bikes.json"
    config = GeometryStoreConfig(token=token, owner=owner, repo=repo, branch=branch, path=path)
    return config if config.configured else None


def normalize_bike_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Usuwa metadane i zapewnia stabilną reprezentację rekordu roweru."""
    result = dict(payload)
    result["name"] = " ".join(str(result.get("name", "Własna geometria")).split())[:120] or "Własna geometria"
    result["bike_type"] = " ".join(str(result.get("bike_type", "Gravel")).split())[:30] or "Gravel"
    # Metadane są zapisywane obok geometrii, ale BikeGeometry je zignoruje.
    result.pop("_saved_at", None)
    result.pop("_saved_by", None)
    return result


def merge_bike_payloads(existing: list[Mapping[str, Any]], new_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized_new = normalize_bike_payload(new_payload)
    key = normalized_new["name"].casefold()
    merged: list[dict[str, Any]] = []
    replaced = False
    for item in existing:
        normalized = normalize_bike_payload(item)
        if normalized["name"].casefold() == key:
            if not replaced:
                merged.append(normalized_new)
                replaced = True
        else:
            merged.append(normalized)
    if not replaced:
        merged.append(normalized_new)
    merged.sort(key=lambda item: item["name"].casefold())
    return merged


def parse_store_document(raw: bytes | str | None) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    if not text.strip():
        return []
    payload = json.loads(text)
    if isinstance(payload, list):
        bikes = payload
    elif isinstance(payload, dict):
        bikes = payload.get("bikes", [])
    else:
        raise SharedStoreError("Plik wspólnej bazy ma nieprawidłowy format.")
    if not isinstance(bikes, list):
        raise SharedStoreError("Pole 'bikes' w bazie nie jest listą.")
    return [normalize_bike_payload(item) for item in bikes if isinstance(item, Mapping)]


def build_store_document(bikes: list[Mapping[str, Any]], saved_by: str = "") -> bytes:
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "saved_by": " ".join(saved_by.split())[:40],
        "bikes": [normalize_bike_payload(item) for item in bikes],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    data: bytes | None,
    timeout: float,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()
    except urllib.error.URLError as exc:
        raise SharedStoreError(f"Nie udało się połączyć ze wspólną bazą: {exc.reason}") from exc


def _api_url(config: GeometryStoreConfig) -> str:
    path = "/".join(urllib.parse.quote(segment, safe="") for segment in config.path.split("/"))
    return f"https://api.github.com/repos/{urllib.parse.quote(config.owner, safe='')}/{urllib.parse.quote(config.repo, safe='')}/contents/{path}"


def _headers(config: GeometryStoreConfig) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BikeFit-Studio-Online",
        "Content-Type": "application/json; charset=utf-8",
    }


def load_remote_bikes(
    config: GeometryStoreConfig,
    *,
    transport: Transport = _default_transport,
    timeout: float = 12.0,
) -> tuple[list[dict[str, Any]], str | None]:
    url = _api_url(config) + "?ref=" + urllib.parse.quote(config.branch, safe="")
    status, raw = transport("GET", url, _headers(config), None, timeout)
    if status == 404:
        return [], None
    if status != 200:
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Odczyt wspólnej bazy nie powiódł się (HTTP {status}): {detail}")
    try:
        payload = json.loads(raw.decode("utf-8"))
        encoded = str(payload.get("content", "")).replace("\n", "")
        content = base64.b64decode(encoded) if encoded else b""
        bikes = parse_store_document(content)
        sha = str(payload.get("sha") or "") or None
        return bikes, sha
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SharedStoreError("Nie udało się odczytać zawartości wspólnej bazy.") from exc


def save_remote_bike(
    config: GeometryStoreConfig,
    bike_payload: Mapping[str, Any],
    *,
    saved_by: str = "",
    transport: Transport = _default_transport,
    timeout: float = 12.0,
    retries: int = 3,
) -> list[dict[str, Any]]:
    last_error: str | None = None
    for attempt in range(max(1, retries)):
        bikes, sha = load_remote_bikes(config, transport=transport, timeout=timeout)
        merged = merge_bike_payloads(bikes, bike_payload)
        document = build_store_document(merged, saved_by=saved_by)
        body: dict[str, Any] = {
            "message": f"Dodaj geometrię: {normalize_bike_payload(bike_payload)['name']}",
            "content": base64.b64encode(document).decode("ascii"),
            "branch": config.branch,
        }
        if sha:
            body["sha"] = sha
        status, raw = transport(
            "PUT",
            _api_url(config),
            _headers(config),
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout,
        )
        if status in (200, 201):
            return merged
        if status in (409, 422) and attempt + 1 < retries:
            # Ktoś zapisał plik pomiędzy GET i PUT. Pobieramy nowy SHA i ponawiamy.
            time.sleep(0.15 * (attempt + 1))
            last_error = f"konflikt HTTP {status}"
            continue
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Zapis wspólnej geometrii nie powiódł się (HTTP {status}): {detail}")
    raise SharedStoreError(f"Nie udało się zapisać po ponowieniach: {last_error or 'nieznany błąd'}")


def load_local_bikes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return parse_store_document(path.read_bytes())
    except (OSError, json.JSONDecodeError, SharedStoreError):
        return []


def save_local_bike(path: Path, bike_payload: Mapping[str, Any], saved_by: str = "") -> list[dict[str, Any]]:
    bikes = merge_bike_payloads(load_local_bikes(path), bike_payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(build_store_document(bikes, saved_by=saved_by))
    tmp.replace(path)
    return bikes
