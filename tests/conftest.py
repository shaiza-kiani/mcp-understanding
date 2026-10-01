from __future__ import annotations

from typing import Any, Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from owm import OpenWeatherClient

Handler = Callable[[httpx.Request], httpx.Response]

LONDON_PAYLOAD: dict[str, Any] = {
    "coord": {"lon": -0.1257, "lat": 51.5085},
    "weather": [{"id": 803, "main": "Clouds", "description": "broken clouds", "icon": "04d"}],
    "base": "stations",
    "main": {
        "temp": 11.4,
        "feels_like": 10.9,
        "temp_min": 10.4,
        "temp_max": 12.0,
        "pressure": 1016,
        "humidity": 82,
    },
    "visibility": 10000,
    "wind": {"speed": 4.63, "deg": 250},
    "clouds": {"all": 75},
    "dt": 1699999999,
    "sys": {
        "type": 2,
        "id": 5091,
        "country": "GB",
        "sunrise": 1699956000,
        "sunset": 1699990000,
        "session": 1699999999,
    },
    "timezone": 0,
    "id": 2643743,
    "name": "London",
    "cod": 200,
}


def json_handler(payload: Any, status_code: int = 200) -> Handler:
    return lambda request: httpx.Response(status_code, json=payload)


def raw_handler(body: str, status_code: int = 200) -> Handler:
    return lambda request: httpx.Response(status_code, text=body)


def raising_handler(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


def build_client(handler: Handler, units: str = "metric") -> OpenWeatherClient:
    """An OpenWeatherClient whose transport is in-process instead of the network."""
    client = OpenWeatherClient(
        api_key="test-key", base_url="https://api.openweathermap.org", units=units, lang="en"
    )
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


@pytest.fixture(autouse=True)
def env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEATHER_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def default_units(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OWM_UNITS", "metric")


@pytest.fixture
def client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    """TestClient over the real app; the provider is faked at the transport layer.

    Tests that need a different provider behaviour parametrise ``client``
    indirectly with a handler, e.g. ``@pytest.mark.parametrize("client", [...], indirect=True)``.
    """
    handler = getattr(request, "param", json_handler(LONDON_PAYLOAD))
    main.app.dependency_overrides[main.get_client] = lambda: build_client(handler)
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()