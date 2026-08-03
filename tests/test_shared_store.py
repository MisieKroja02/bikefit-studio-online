from __future__ import annotations

import base64
import json
from pathlib import Path

from bikefit.shared_store import (
    GeometryStoreConfig,
    build_store_document,
    config_from_mapping,
    load_local_bikes,
    load_remote_bikes,
    merge_bike_payloads,
    parse_store_document,
    save_local_bike,
    save_remote_bike,
)


def sample(name: str, stack: float = 575.0) -> dict:
    return {
        "name": name,
        "bike_type": "Gravel",
        "stack": stack,
        "reach": 385.0,
    }


def test_config_mapping_requires_token_owner_repo() -> None:
    assert config_from_mapping({}) is None
    assert config_from_mapping({"token": "x", "owner": "o", "repo": "r"}) is not None


def test_merge_replaces_case_insensitively_and_sorts() -> None:
    merged = merge_bike_payloads([sample("Zulu"), sample("alpha", 500)], sample("ALPHA", 610))
    assert [item["name"] for item in merged] == ["ALPHA", "Zulu"]
    assert merged[0]["stack"] == 610


def test_store_document_roundtrip() -> None:
    raw = build_store_document([sample("Test")], saved_by="Robert")
    parsed = parse_store_document(raw)
    assert parsed == [sample("Test")]


def test_local_store_persists_across_reads(tmp_path: Path) -> None:
    path = tmp_path / "community.json"
    save_local_bike(path, sample("Pierwszy"), "a")
    save_local_bike(path, sample("Drugi"), "b")
    loaded = load_local_bikes(path)
    assert {item["name"] for item in loaded} == {"Pierwszy", "Drugi"}


def test_remote_create_and_load() -> None:
    config = GeometryStoreConfig("token", "owner", "repo")
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


def test_remote_load_decodes_github_content() -> None:
    config = GeometryStoreConfig("token", "owner", "repo")
    encoded = base64.b64encode(build_store_document([sample("Zdalny")])).decode("ascii")

    def transport(method, url, headers, data, timeout):
        return 200, json.dumps({"sha": "abc", "content": encoded}).encode("utf-8")

    bikes, sha = load_remote_bikes(config, transport=transport)
    assert sha == "abc"
    assert bikes[0]["name"] == "Zdalny"


def test_remote_conflict_retries_with_new_sha() -> None:
    config = GeometryStoreConfig("token", "owner", "repo")
    calls = {"get": 0, "put": 0}

    def transport(method, url, headers, data, timeout):
        if method == "GET":
            calls["get"] += 1
            current = [sample("Inny")] if calls["get"] == 1 else [sample("Inny"), sample("Dodany równolegle")]
            encoded = base64.b64encode(build_store_document(current)).decode("ascii")
            return 200, json.dumps({"sha": f"sha{calls['get']}", "content": encoded}).encode()
        calls["put"] += 1
        if calls["put"] == 1:
            return 409, b'{"message":"sha conflict"}'
        return 200, b'{}'

    result = save_remote_bike(config, sample("Mój"), transport=transport, retries=3)
    assert calls == {"get": 2, "put": 2}
    assert {item["name"] for item in result} == {"Inny", "Dodany równolegle", "Mój"}
