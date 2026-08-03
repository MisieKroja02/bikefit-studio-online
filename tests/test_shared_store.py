from __future__ import annotations

import base64
import json
from pathlib import Path

from bikefit.shared_store import (
    GeometryStoreConfig,
    build_geometry_document,
    build_store_document,
    config_from_mapping,
    delete_local_geometry_file,
    delete_remote_bike,
    geometry_filename,
    load_local_bikes,
    load_local_geometry_folder,
    load_remote_bikes,
    merge_bike_payloads,
    parse_geometry_document,
    parse_store_document,
    save_local_bike,
    save_local_geometry_file,
    save_remote_bike,
)


def sample(name: str, stack: float = 575.0) -> dict:
    return {
        "name": name,
        "bike_type": "Gravel",
        "stack": stack,
        "reach": 385.0,
    }


def github_file_response(content: bytes, sha: str = "abc") -> bytes:
    return json.dumps({"sha": sha, "content": base64.b64encode(content).decode("ascii")}).encode()


def test_config_mapping_requires_token_owner_repo() -> None:
    assert config_from_mapping({}) is None
    config = config_from_mapping({"token": "x", "owner": "o", "repo": "r"})
    assert config is not None
    assert config.path == "geometries"
    assert config.folder_mode


def test_merge_replaces_case_insensitively_and_sorts() -> None:
    merged = merge_bike_payloads([sample("Zulu"), sample("alpha", 500)], sample("ALPHA", 610))
    assert [item["name"] for item in merged] == ["ALPHA", "Zulu"]
    assert merged[0]["stack"] == 610


def test_store_document_roundtrip() -> None:
    raw = build_store_document([sample("Test")], saved_by="Robert")
    parsed = parse_store_document(raw)
    assert parsed == [sample("Test")]


def test_geometry_document_roundtrip_and_stable_filename() -> None:
    raw = build_geometry_document(sample("KROSS Esker 7.0 2025 M"), saved_by="Robert")
    parsed = parse_geometry_document(raw)
    assert parsed == sample("KROSS Esker 7.0 2025 M")
    assert geometry_filename("KROSS Esker 7.0 2025 M") == geometry_filename("KROSS Esker 7.0 2025 M")
    assert geometry_filename("ŁÓDŹ Gravel").endswith(".json")


def test_local_store_persists_across_reads(tmp_path: Path) -> None:
    path = tmp_path / "community.json"
    save_local_bike(path, sample("Pierwszy"), "a")
    save_local_bike(path, sample("Drugi"), "b")
    loaded = load_local_bikes(path)
    assert {item["name"] for item in loaded} == {"Pierwszy", "Drugi"}

def test_local_folder_saves_each_geometry_separately(tmp_path: Path) -> None:
    folder = tmp_path / "geometries"
    save_local_geometry_file(folder, sample("Pierwszy"), "a")
    save_local_geometry_file(folder, sample("Drugi"), "b")
    files = list(folder.glob("*.json"))
    assert len(files) == 2
    loaded = load_local_geometry_folder(folder)
    assert {item["name"] for item in loaded} == {"Pierwszy", "Drugi"}


def test_remote_legacy_create_and_load() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="community.json")
    requests: list[tuple[str, str, bytes | None]] = []

    def transport(method, url, headers, data, timeout):
        requests.append((method, url, data))
        if method == "GET":
            return 404, b'{"message":"Not Found"}'
        body = json.loads(data.decode("utf-8"))
        content = base64.b64decode(body["content"])
        assert parse_store_document(content)[0]["name"] == "Nowy"
        return 201, b'{"content":{"sha":"new"}}'

    merged = save_remote_bike(config, sample("Nowy"), transport=transport)
    assert merged[0]["name"] == "Nowy"
    assert [item[0] for item in requests] == ["GET", "PUT"]


def test_remote_legacy_load_decodes_github_content() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="community.json")
    encoded = github_file_response(build_store_document([sample("Zdalny")]))

    def transport(method, url, headers, data, timeout):
        return 200, encoded

    bikes, sha = load_remote_bikes(config, transport=transport)
    assert sha == "abc"
    assert bikes[0]["name"] == "Zdalny"


def test_remote_legacy_conflict_retries_with_new_sha() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="community.json")
    calls = {"get": 0, "put": 0}

    def transport(method, url, headers, data, timeout):
        if method == "GET":
            calls["get"] += 1
            current = [sample("Inny")] if calls["get"] == 1 else [sample("Inny"), sample("Dodany równolegle")]
            return 200, github_file_response(build_store_document(current), f"sha{calls['get']}")
        calls["put"] += 1
        if calls["put"] == 1:
            return 409, b'{"message":"sha conflict"}'
        return 200, b'{}'

    result = save_remote_bike(config, sample("Mój"), transport=transport, retries=3)
    assert calls == {"get": 2, "put": 2}
    assert {item["name"] for item in result} == {"Inny", "Dodany równolegle", "Mój"}


def test_remote_folder_lists_and_reads_separate_files() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="geometries", legacy_path="")
    entries = [
        {"type": "file", "name": "a.json", "path": "geometries/a.json"},
        {"type": "file", "name": "b.json", "path": "geometries/b.json"},
        {"type": "file", "name": "README.md", "path": "geometries/README.md"},
    ]

    def transport(method, url, headers, data, timeout):
        if url.endswith("/contents/geometries?ref=main"):
            return 200, json.dumps(entries).encode()
        if "a.json" in url:
            return 200, github_file_response(build_geometry_document(sample("Alpha")))
        if "b.json" in url:
            return 200, github_file_response(build_geometry_document(sample("Beta")))
        raise AssertionError(url)

    bikes, sha = load_remote_bikes(config, transport=transport)
    assert sha is None
    assert [b["name"] for b in bikes] == ["Alpha", "Beta"]


def test_remote_folder_saves_one_geometry_file() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="geometries", legacy_path="")
    stored: dict[str, bytes] = {}
    target_name = geometry_filename("Nowy rower")

    def transport(method, url, headers, data, timeout):
        if method == "GET" and url.endswith("/contents/geometries?ref=main"):
            entries = [
                {"type": "file", "name": name, "path": f"geometries/{name}"}
                for name in stored
            ]
            return (200, json.dumps(entries).encode()) if entries else (404, b'{}')
        if method == "GET" and target_name in url:
            if target_name not in stored:
                return 404, b'{}'
            return 200, github_file_response(stored[target_name])
        if method == "PUT" and target_name in url:
            body = json.loads(data.decode())
            stored[target_name] = base64.b64decode(body["content"])
            return 201, b'{}'
        raise AssertionError((method, url))

    result = save_remote_bike(config, sample("Nowy rower"), transport=transport)
    assert target_name in stored
    assert parse_geometry_document(stored[target_name])["name"] == "Nowy rower"
    assert [b["name"] for b in result] == ["Nowy rower"]


def test_folder_mode_also_reads_legacy_file_for_migration() -> None:
    config = GeometryStoreConfig(
        "token", "owner", "repo", path="geometries", legacy_path="community_bikes.json"
    )

    def transport(method, url, headers, data, timeout):
        if url.endswith("/contents/geometries?ref=main"):
            return 404, b'{}'
        if "community_bikes.json" in url:
            return 200, github_file_response(build_store_document([sample("Stary zapis")]))
        raise AssertionError(url)

    bikes, _ = load_remote_bikes(config, transport=transport)
    assert [b["name"] for b in bikes] == ["Stary zapis"]


def test_local_folder_deletes_geometry_and_legacy_entry(tmp_path: Path) -> None:
    folder = tmp_path / "geometries"
    legacy = tmp_path / "community.json"
    save_local_geometry_file(folder, sample("Do usunięcia"), "a")
    save_local_bike(legacy, sample("Do usunięcia"), "a")
    assert delete_local_geometry_file(folder, "Do usunięcia", legacy_file=legacy)
    assert load_local_geometry_folder(folder, legacy) == []


def test_remote_folder_deletes_geometry_file() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="geometries", legacy_path="")
    target_name = geometry_filename("Do usunięcia")
    calls = []

    def transport(method, url, headers, data, timeout):
        calls.append((method, url))
        if method == "GET" and target_name in url:
            return 200, github_file_response(build_geometry_document(sample("Do usunięcia")), "sha-del")
        if method == "DELETE" and target_name in url:
            body = json.loads(data.decode())
            assert body["sha"] == "sha-del"
            return 200, b'{}'
        raise AssertionError((method, url))

    assert delete_remote_bike(config, "Do usunięcia", transport=transport)
    assert [method for method, _url in calls] == ["GET", "DELETE"]


def test_remote_single_file_deletes_only_matching_geometry() -> None:
    config = GeometryStoreConfig("token", "owner", "repo", path="community.json")

    def transport(method, url, headers, data, timeout):
        if method == "GET":
            return 200, github_file_response(build_store_document([sample("Zostaje"), sample("Usuń")]), "sha1")
        if method == "PUT":
            body = json.loads(data.decode())
            remaining = parse_store_document(base64.b64decode(body["content"]))
            assert [item["name"] for item in remaining] == ["Zostaje"]
            return 200, b'{}'
        raise AssertionError((method, url))

    assert delete_remote_bike(config, "Usuń", transport=transport)
