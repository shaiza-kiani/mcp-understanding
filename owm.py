from __future__ import annotations

from typing import Any

import httpx


class WeatherAPIError(Exception):
    """Upstream returned something we cannot use."""


class WeatherNotFoundError(WeatherAPIError):
    """Requested city does not exist."""


class WeatherAuthError(WeatherAPIError):
    """API key rejected."""


class OpenWeatherClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        units: str = "metric",
        lang: str = "en",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._units = units
        self._lang = lang
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_current(self, city: str) -> dict[str, Any]:
        params = {"q": city, "appid": self._api_key, "units": self._units, "lang": self._lang}
        try:
            response = await self._client.get(f"{self._base_url}/data/2.5/weather", params=params)
        except httpx.TimeoutException as exc:
            raise WeatherAPIError("Weather provider timed out") from exc
        except httpx.HTTPError as exc:
            raise WeatherAPIError("Could not reach weather provider") from exc

        if response.status_code == 401:
            raise WeatherAuthError("Invalid or inactive API key")
        if response.status_code == 404:
            raise WeatherNotFoundError(f"City not found: {city}")

        if response.status_code >= 400:
            detail = _extract_message(response)
            if response.status_code == 429:
                raise WeatherAPIError("Weather provider rate limit reached")
            raise WeatherAPIError(f"Weather provider error {response.status_code}: {detail}")

        try:
            return response.json()
        except ValueError as exc:
            raise WeatherAPIError("Weather provider returned non-JSON response") from exc


def _extract_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("message") or body.get("cod") or "unknown error")
    return "unknown error"


def to_weather_response(payload: dict[str, Any], units: str) -> dict[str, Any]:
    """Normalise an OpenWeatherMap payload into our public shape."""
    sys_block = payload.get("sys") or {}
    main_block = payload.get("main") or {}
    coord = payload.get("coord") or {}

    return {
        "city": payload.get("name") or "Unknown",
        "country": sys_block.get("country"),
        "coordinates": {"lat": coord.get("lat"), "lon": coord.get("lon")} if coord else None,
        "observed_at": payload.get("dt") or 0,
        "conditions": payload.get("weather") or [],
        "temperature": main_block,
        "wind": payload.get("wind") or {"speed": 0.0},
        "clouds": payload.get("clouds"),
        "rain": payload.get("rain"),
        "snow": payload.get("snow"),
        "visibility": payload.get("visibility"),
        "humidity": main_block.get("humidity", 0),
        "units": units,
    }