from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from owm import WeatherAuthError, WeatherNotFoundError
from tests.conftest import (
    LONDON_PAYLOAD,
    Handler,
    build_client,
    json_handler,
    raising_handler,
    raw_handler,
)


# --- happy path -------------------------------------------------------------


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_weather_returns_normalised_payload(client: TestClient) -> None:
    r = client.get("/weather", params={"city": "London"})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "London"
    assert body["country"] == "GB"
    assert body["units"] == "metric"
    assert body["temperature"]["temp"] == 11.4
    assert body["temperature"]["feels_like"] == 10.9
    assert body["humidity"] == 82
    assert body["conditions"][0]["description"] == "broken clouds"
    assert body["coordinates"] == {"lat": 51.5085, "lon": -0.1257}
    assert body["wind"] == {"speed": 4.63, "deg": 250.0}


@pytest.mark.parametrize(
    "client",
    [json_handler({k: v for k, v in LONDON_PAYLOAD.items() if k not in {"clouds", "sys"}})],
    indirect=True,
)
def test_missing_sys_and_clouds_are_omitted(client: TestClient) -> None:
    body = client.get("/weather", params={"city": "London"}).json()
    assert "clouds" not in body
    assert "country" not in body
    assert body["city"] == "London"


@pytest.mark.parametrize(
    "client",
    [json_handler({k: v for k, v in LONDON_PAYLOAD.items() if k not in {"rain", "snow"}})],
    indirect=True,
)
def test_missing_rain_and_snow_are_omitted(client: TestClient) -> None:
    body = client.get("/weather", params={"city": "London"}).json()
    assert "rain" not in body
    assert "snow" not in body
    assert body["country"] == "GB"


def test_api_key_is_not_leaked_in_response(client: TestClient) -> None:
    assert "test-key" not in client.get("/weather", params={"city": "London"}).text


# --- input validation -------------------------------------------------------


def test_weather_requires_city(client: TestClient) -> None:
    assert client.get("/weather").status_code == 422


@pytest.mark.parametrize("city", ["", "   ", "x" * 200])
def test_weather_rejects_bad_city_values(client: TestClient, city: str) -> None:
    assert client.get("/weather", params={"city": city}).status_code == 422


# --- provider error mapping ------------------------------------------------


@pytest.mark.parametrize(
    "client",
    [json_handler({"cod": "404", "message": "city not found"}, 404)],
    indirect=True,
)
def test_unknown_city_returns_404(client: TestClient) -> None:
    r = client.get("/weather", params={"city": "Atlantis"})
    assert r.status_code == 404
    assert r.json()["detail"] == "City not found: Atlantis"


@pytest.mark.parametrize(
    "client",
    [json_handler({"cod": 401, "message": "Invalid API key."}, 401)],
    indirect=True,
)
def test_bad_api_key_returns_500(client: TestClient) -> None:
    r = client.get("/weather", params={"city": "London"})
    assert r.status_code == 500
    assert r.json()["detail"] == "Server API key is invalid"


@pytest.mark.parametrize(
    "client",
    [json_handler({"cod": 429, "message": "call limit exceeded"}, 429)],
    indirect=True,
)
def test_rate_limit_returns_502(client: TestClient) -> None:
    assert client.get("/weather", params={"city": "London"}).status_code == 502


@pytest.mark.parametrize("client", [raw_handler("boom", 500)], indirect=True)
def test_upstream_5xx_returns_502(client: TestClient) -> None:
    assert client.get("/weather", params={"city": "London"}).status_code == 502


@pytest.mark.parametrize(
    "client",
    [
        raising_handler(httpx.ReadTimeout("timed out")),
        raising_handler(httpx.ConnectError("no route")),
    ],
    indirect=True,
)
def test_transport_failure_returns_502(client: TestClient) -> None:
    assert client.get("/weather", params={"city": "London"}).status_code == 502


@pytest.mark.parametrize(
    "client",
    [raw_handler("<html>maintenance</html>")],
    indirect=True,
)
def test_non_json_upstream_returns_502(client: TestClient) -> None:
    assert client.get("/weather", params={"city": "London"}).status_code == 502


@pytest.mark.parametrize(
    "client",
    [json_handler({"totally": "unexpected"})],
    indirect=True,
)
def test_malformed_payload_returns_502(client: TestClient) -> None:
    r = client.get("/weather", params={"city": "London"})
    assert r.status_code == 502
    assert "Unexpected provider payload" in r.json()["detail"]


# --- client unit tests ------------------------------------------------------


def test_query_params_are_forwarded_upstream() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=LONDON_PAYLOAD)

    fake = build_client(handler, units="imperial")
    result = asyncio.run(fake.get_current("Tokyo"))
    asyncio.run(fake.aclose())

    assert seen["q"] == "Tokyo"
    assert seen["appid"] == "test-key"
    assert seen["units"] == "imperial"
    assert result["name"] == "London"


def test_city_is_stripped_before_reaching_provider() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=LONDON_PAYLOAD)

    fake = build_client(handler)
    asyncio.run(fake.get_current("Tokyo"))
    asyncio.run(fake.aclose())

    assert seen["q"] == "Tokyo"


def test_endpoint_strips_surrounding_whitespace(client: TestClient) -> None:
    """Padding is removed before the provider call, and the request still succeeds."""
    assert client.get("/weather", params={"city": "  London  "}).status_code == 200


def test_client_raises_specific_errors() -> None:
    not_found = build_client(json_handler({"cod": "404"}, 404))
    auth = build_client(json_handler({"cod": 401}, 401))

    with pytest.raises(WeatherNotFoundError):
        asyncio.run(not_found.get_current("Atlantis"))
    with pytest.raises(WeatherAuthError):
        asyncio.run(auth.get_current("London"))

    asyncio.run(not_found.aclose())
    asyncio.run(auth.aclose())


@pytest.mark.parametrize(
    "handler",
    [
        json_handler({"cod": "404"}, 404),
        json_handler({"cod": 401}, 401),
        json_handler({"cod": 429}, 429),
        raw_handler("nope", 500),
        raw_handler("not json"),
        raising_handler(httpx.ReadTimeout("t")),
    ],
)
def test_no_handler_leaks_unexpected_exception_type(handler: Handler) -> None:
    from owm import WeatherAPIError

    fake = build_client(handler)
    with pytest.raises(WeatherAPIError):
        asyncio.run(fake.get_current("London"))
    asyncio.run(fake.aclose())