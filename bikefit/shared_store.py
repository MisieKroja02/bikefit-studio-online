from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import unicodedata
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
    # Gdy path kończy się .json, używany jest zgodny wstecznie magazyn jednoplikowy.
    # W przeciwnym razie każda geometria trafia do osobnego pliku w tym folderze.
    path: str = "geometries"
    legacy_path: str = "community_bikes.json"

    @property
    def configured(self) -> bool:
        return bool(self.token.strip() and self.owner.strip() and self.repo.strip())

    @property
    def folder_mode(self) -> bool:
        return not self.path.strip().lower().endswith(".json")


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, bytes]]


def config_from_mapping(mapping: Mapping[str, Any] | None) -> GeometryStoreConfig | None:
    if not mapping:
        return None
    token = str(mapping.get("token", "")).strip()
    owner = str(mapping.get("owner", "")).strip()
    repo = str(mapping.get("repo", "")).strip()
    branch = str(mapping.get("branch", "main")).strip() or "main"
    path = str(mapping.get("path", "geometries")).strip().strip("/") or "geometries"
    legacy_path = str(mapping.get("legacy_path", "community_bikes.json")).strip().strip("/")
    config = GeometryStoreConfig(
        token=token,
        owner=owner,
        repo=repo,
        branch=branch,
        path=path,
        legacy_path=legacy_path,
    )
    return config if config.configured else None


def normalize_bike_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Usuwa metadane i zapewnia stabilną reprezentację rekordu roweru."""
    result = dict(payload)
    result["name"] = " ".join(str(result.get("name", "Własna geometria")).split())[:120] or "Własna geometria"
    result["bike_type"] = " ".join(str(result.get("bike_type", "Gravel")).split())[:30] or "Gravel"
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




def remove_bike_payloads(existing: list[Mapping[str, Any]], bike_name: str) -> tuple[list[dict[str, Any]], bool]:
    """Usuwa geometrię po nazwie, bez rozróżniania wielkości liter."""
    key = " ".join(str(bike_name or "").split()).casefold()
    kept: list[dict[str, Any]] = []
    removed = False
    for item in existing:
        normalized = normalize_bike_payload(item)
        if normalized["name"].casefold() == key:
            removed = True
            continue
        kept.append(normalized)
    kept.sort(key=lambda item: item["name"].casefold())
    return kept, removed

def parse_store_document(raw: bytes | str | None) -> list[dict[str, Any]]:
    """Czyta starszy dokument zawierający listę geometrii."""
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
    """Buduje starszy dokument zbiorczy, zachowany dla zgodności wstecznej."""
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "saved_by": " ".join(saved_by.split())[:40],
        "bikes": [normalize_bike_payload(item) for item in bikes],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def build_geometry_document(bike: Mapping[str, Any], saved_by: str = "") -> bytes:
    """Buduje pojedynczy plik geometrii zapisywany w folderze geometries/."""
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "saved_by": " ".join(saved_by.split())[:40],
        "bike": normalize_bike_payload(bike),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def parse_geometry_document(raw: bytes | str | None) -> dict[str, Any]:
    if raw is None:
        raise SharedStoreError("Pusty plik geometrii.")
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    payload = json.loads(text)
    if isinstance(payload, Mapping) and isinstance(payload.get("bike"), Mapping):
        return normalize_bike_payload(payload["bike"])
    # Akceptujemy również bezpośredni rekord BikeGeometry.
    if isinstance(payload, Mapping) and "name" in payload:
        return normalize_bike_payload(payload)
    raise SharedStoreError("Plik geometrii ma nieprawidłowy format.")


def geometry_filename(name: str) -> str:
    """Stabilna, czytelna nazwa pliku; ta sama nazwa roweru nadpisuje ten sam plik."""
    cleaned = " ".join(str(name or "Własna geometria").split()) or "Własna geometria"
    ascii_name = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()[:70] or "geometria"
    suffix = hashlib.sha1(cleaned.casefold().encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{suffix}.json"


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


def _api_url_for_path(config: GeometryStoreConfig, path: str) -> str:
    encoded = "/".join(urllib.parse.quote(segment, safe="") for segment in path.strip("/").split("/"))
    return (
        f"https://api.github.com/repos/{urllib.parse.quote(config.owner, safe='')}/"
        f"{urllib.parse.quote(config.repo, safe='')}/contents/{encoded}"
    )


def _api_url(config: GeometryStoreConfig) -> str:
    return _api_url_for_path(config, config.path)


def _headers(config: GeometryStoreConfig) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BikeFit-Studio-Online",
        "Content-Type": "application/json; charset=utf-8",
    }


def _decode_github_file(raw: bytes) -> tuple[bytes, str | None]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        encoded = str(payload.get("content", "")).replace("\n", "")
        content = base64.b64decode(encoded) if encoded else b""
        sha = str(payload.get("sha") or "") or None
        return content, sha
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SharedStoreError("Nie udało się odczytać zawartości pliku GitHub.") from exc


def _load_remote_single_file(
    config: GeometryStoreConfig,
    path: str,
    *,
    transport: Transport,
    timeout: float,
) -> tuple[list[dict[str, Any]], str | None]:
    url = _api_url_for_path(config, path) + "?ref=" + urllib.parse.quote(config.branch, safe="")
    status, raw = transport("GET", url, _headers(config), None, timeout)
    if status == 404:
        return [], None
    if status != 200:
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Odczyt wspólnej bazy nie powiódł się (HTTP {status}): {detail}")
    content, sha = _decode_github_file(raw)
    return parse_store_document(content), sha


def _load_remote_folder(
    config: GeometryStoreConfig,
    *,
    transport: Transport,
    timeout: float,
) -> list[dict[str, Any]]:
    directory_url = _api_url(config) + "?ref=" + urllib.parse.quote(config.branch, safe="")
    status, raw = transport("GET", directory_url, _headers(config), None, timeout)
    if status == 404:
        return []
    if status != 200:
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Odczyt folderu geometrii nie powiódł się (HTTP {status}): {detail}")
    try:
        entries = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SharedStoreError("Lista plików folderu geometrii ma nieprawidłowy format.") from exc
    if not isinstance(entries, list):
        raise SharedStoreError("Ścieżka wspólnej bazy nie jest folderem.")

    bikes: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("type") != "file" or not str(entry.get("name", "")).lower().endswith(".json"):
            continue
        entry_path = str(entry.get("path") or "").strip()
        if not entry_path:
            continue
        file_url = _api_url_for_path(config, entry_path) + "?ref=" + urllib.parse.quote(config.branch, safe="")
        file_status, file_raw = transport("GET", file_url, _headers(config), None, timeout)
        if file_status != 200:
            continue
        try:
            content, _sha = _decode_github_file(file_raw)
            bikes.append(parse_geometry_document(content))
        except (SharedStoreError, json.JSONDecodeError):
            continue
    bikes.sort(key=lambda item: str(item.get("name", "")).casefold())
    return bikes


def load_remote_bikes(
    config: GeometryStoreConfig,
    *,
    transport: Transport = _default_transport,
    timeout: float = 12.0,
) -> tuple[list[dict[str, Any]], str | None]:
    """Ładuje folder geometrii albo starszy plik zbiorczy.

    W trybie folderowym dodatkowo odczytuje opcjonalny legacy_path, aby wcześniej
    zapisane geometrie nie zniknęły po przejściu na nowy układ.
    """
    if not config.folder_mode:
        return _load_remote_single_file(config, config.path, transport=transport, timeout=timeout)

    folder_bikes = _load_remote_folder(config, transport=transport, timeout=timeout)
    merged = folder_bikes
    if config.legacy_path and config.legacy_path != config.path:
        try:
            legacy_bikes, _legacy_sha = _load_remote_single_file(
                config, config.legacy_path, transport=transport, timeout=timeout
            )
            for bike in legacy_bikes:
                merged = merge_bike_payloads(merged, bike)
        except SharedStoreError:
            # Uszkodzony lub niedostępny plik migracyjny nie blokuje folderu.
            pass
    return merged, None


def _save_remote_single_file(
    config: GeometryStoreConfig,
    bike_payload: Mapping[str, Any],
    *,
    saved_by: str,
    transport: Transport,
    timeout: float,
    retries: int,
) -> list[dict[str, Any]]:
    last_error: str | None = None
    for attempt in range(max(1, retries)):
        bikes, sha = _load_remote_single_file(
            config, config.path, transport=transport, timeout=timeout
        )
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
            time.sleep(0.15 * (attempt + 1))
            last_error = f"konflikt HTTP {status}"
            continue
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Zapis wspólnej geometrii nie powiódł się (HTTP {status}): {detail}")
    raise SharedStoreError(f"Nie udało się zapisać po ponowieniach: {last_error or 'nieznany błąd'}")


def _save_remote_folder_file(
    config: GeometryStoreConfig,
    bike_payload: Mapping[str, Any],
    *,
    saved_by: str,
    transport: Transport,
    timeout: float,
    retries: int,
) -> list[dict[str, Any]]:
    normalized = normalize_bike_payload(bike_payload)
    filename = geometry_filename(str(normalized["name"]))
    file_path = f"{config.path.strip('/')}/{filename}"
    file_url = _api_url_for_path(config, file_path)
    last_error: str | None = None

    for attempt in range(max(1, retries)):
        get_url = file_url + "?ref=" + urllib.parse.quote(config.branch, safe="")
        status, raw = transport("GET", get_url, _headers(config), None, timeout)
        sha: str | None = None
        if status == 200:
            _content, sha = _decode_github_file(raw)
        elif status != 404:
            detail = raw.decode("utf-8", errors="replace")[:300]
            raise SharedStoreError(f"Sprawdzenie pliku geometrii nie powiodło się (HTTP {status}): {detail}")

        body: dict[str, Any] = {
            "message": f"Zapisz geometrię: {normalized['name']}",
            "content": base64.b64encode(build_geometry_document(normalized, saved_by=saved_by)).decode("ascii"),
            "branch": config.branch,
        }
        if sha:
            body["sha"] = sha
        put_status, put_raw = transport(
            "PUT",
            file_url,
            _headers(config),
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout,
        )
        if put_status in (200, 201):
            bikes, _ = load_remote_bikes(config, transport=transport, timeout=timeout)
            return bikes
        if put_status in (409, 422) and attempt + 1 < retries:
            time.sleep(0.15 * (attempt + 1))
            last_error = f"konflikt HTTP {put_status}"
            continue
        detail = put_raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Zapis pliku geometrii nie powiódł się (HTTP {put_status}): {detail}")
    raise SharedStoreError(f"Nie udało się zapisać po ponowieniach: {last_error or 'nieznany błąd'}")


def save_remote_bike(
    config: GeometryStoreConfig,
    bike_payload: Mapping[str, Any],
    *,
    saved_by: str = "",
    transport: Transport = _default_transport,
    timeout: float = 12.0,
    retries: int = 3,
) -> list[dict[str, Any]]:
    if config.folder_mode:
        return _save_remote_folder_file(
            config,
            bike_payload,
            saved_by=saved_by,
            transport=transport,
            timeout=timeout,
            retries=retries,
        )
    return _save_remote_single_file(
        config,
        bike_payload,
        saved_by=saved_by,
        transport=transport,
        timeout=timeout,
        retries=retries,
    )


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


def load_local_geometry_folder(path: Path, legacy_file: Path | None = None) -> list[dict[str, Any]]:
    """Ładuje osobne pliki geometrii z lokalnego folderu oraz opcjonalny stary plik zbiorczy."""
    bikes: list[dict[str, Any]] = []
    if path.exists() and path.is_dir():
        for file_path in sorted(path.glob("*.json")):
            try:
                bikes = merge_bike_payloads(bikes, parse_geometry_document(file_path.read_bytes()))
            except (OSError, json.JSONDecodeError, SharedStoreError):
                continue
    if legacy_file is not None:
        for bike in load_local_bikes(legacy_file):
            bikes = merge_bike_payloads(bikes, bike)
    return bikes


def save_local_geometry_file(path: Path, bike_payload: Mapping[str, Any], saved_by: str = "") -> list[dict[str, Any]]:
    """Zapisuje jedną geometrię jako osobny plik JSON w lokalnym folderze."""
    normalized = normalize_bike_payload(bike_payload)
    path.mkdir(parents=True, exist_ok=True)
    target = path / geometry_filename(str(normalized["name"]))
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(build_geometry_document(normalized, saved_by=saved_by))
    tmp.replace(target)
    return load_local_geometry_folder(path)


def _rewrite_remote_single_file_without_bike(
    config: GeometryStoreConfig,
    path: str,
    bike_name: str,
    *,
    transport: Transport,
    timeout: float,
) -> bool:
    bikes, sha = _load_remote_single_file(config, path, transport=transport, timeout=timeout)
    filtered, removed = remove_bike_payloads(bikes, bike_name)
    if not removed:
        return False
    if not sha:
        return True
    body = {
        "message": f"Usuń geometrię: {bike_name}",
        "content": base64.b64encode(build_store_document(filtered)).decode("ascii"),
        "branch": config.branch,
        "sha": sha,
    }
    status, raw = transport(
        "PUT",
        _api_url_for_path(config, path),
        _headers(config),
        json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout,
    )
    if status not in (200, 201):
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Usunięcie geometrii ze starszej bazy nie powiodło się (HTTP {status}): {detail}")
    return True


def delete_remote_bike(
    config: GeometryStoreConfig,
    bike_name: str,
    *,
    transport: Transport = _default_transport,
    timeout: float = 12.0,
) -> bool:
    """Usuwa geometrię z trwałej bazy GitHub. W trybie folderowym usuwa osobny plik."""
    if not config.folder_mode:
        return _rewrite_remote_single_file_without_bike(
            config, config.path, bike_name, transport=transport, timeout=timeout
        )

    filename = geometry_filename(bike_name)
    file_path = f"{config.path.strip('/')}/{filename}"
    file_url = _api_url_for_path(config, file_path)
    get_url = file_url + "?ref=" + urllib.parse.quote(config.branch, safe="")
    status, raw = transport("GET", get_url, _headers(config), None, timeout)
    removed = False
    if status == 200:
        _content, sha = _decode_github_file(raw)
        if sha:
            body = {
                "message": f"Usuń geometrię: {bike_name}",
                "sha": sha,
                "branch": config.branch,
            }
            delete_status, delete_raw = transport(
                "DELETE",
                file_url,
                _headers(config),
                json.dumps(body, ensure_ascii=False).encode("utf-8"),
                timeout,
            )
            if delete_status != 200:
                detail = delete_raw.decode("utf-8", errors="replace")[:300]
                raise SharedStoreError(f"Usunięcie pliku geometrii nie powiodło się (HTTP {delete_status}): {detail}")
            removed = True
    elif status != 404:
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise SharedStoreError(f"Sprawdzenie geometrii przed usunięciem nie powiodło się (HTTP {status}): {detail}")

    if config.legacy_path and config.legacy_path != config.path:
        try:
            removed = _rewrite_remote_single_file_without_bike(
                config, config.legacy_path, bike_name, transport=transport, timeout=timeout
            ) or removed
        except SharedStoreError:
            # Brak lub niedostępna starsza baza nie blokuje usunięcia z folderu.
            pass
    return removed


def delete_local_geometry_file(path: Path, bike_name: str, legacy_file: Path | None = None) -> bool:
    """Usuwa lokalny plik geometrii i ewentualny wpis ze starszej bazy zbiorczej."""
    removed = False
    target = path / geometry_filename(bike_name)
    if target.exists():
        target.unlink()
        removed = True
    if legacy_file is not None and legacy_file.exists():
        bikes = load_local_bikes(legacy_file)
        filtered, legacy_removed = remove_bike_payloads(bikes, bike_name)
        if legacy_removed:
            legacy_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = legacy_file.with_suffix(legacy_file.suffix + ".tmp")
            tmp.write_bytes(build_store_document(filtered))
            tmp.replace(legacy_file)
            removed = True
    return removed
