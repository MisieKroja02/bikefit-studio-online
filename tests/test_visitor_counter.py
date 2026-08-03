from __future__ import annotations

import io
import json
import urllib.error

import pytest

from bikefit.visitor_counter import CounterError, counter_value, request_counter


class Response:
    def __init__(self, payload: object):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.raw


def test_counter_value_accepts_common_response_shapes() -> None:
    assert counter_value({"count": 12}) == 12
    assert counter_value({"data": {"up_count": "15"}}) == 15
    assert counter_value({"result": 3.9}) == 3
    assert counter_value({"unknown": 1}) is None


def test_request_counter_builds_increment_url() -> None:
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response({"count": 44})

    value = request_counter(
        "https://api.counterapi.dev/v1",
        "bike fit",
        "visits today",
        True,
        opener=opener,
    )
    assert value == 44
    assert seen["url"].endswith("/bike%20fit/visits%20today/up")


def test_request_counter_handles_network_error() -> None:
    def opener(request, timeout):
        raise urllib.error.URLError("offline")

    with pytest.raises(CounterError):
        request_counter("https://example.test", "ns", "name", False, opener=opener)
