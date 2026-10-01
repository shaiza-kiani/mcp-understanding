"""Live smoke test against the real OpenWeatherMap API.

Skipped automatically when no key is configured, so it is safe to run anywhere.
Run it explicitly with:

    python smoke_test.py "London"
"""

from __future__ import annotations

import asyncio
import sys

from fastapi.testclient import TestClient

from config import get_settings
from main import app


def main(city: str) -> int:
    settings = get_settings()  # raises RuntimeError if WEATHER_API_KEY is unset
    print(f"Key loaded: {settings.WEATHER_API_KEY[:6]}...  units={settings.OWM_UNITS}")

    with TestClient(app) as client:
        health = client.get("/health")
        print(f"/health -> {health.status_code} {health.json()}")

        response = client.get("/weather", params={"city": city})
        print(f"/weather?city={city} -> {response.status_code}")
        print(response.text)
        return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    city = sys.argv[1] if len(sys.argv) > 1 else "London"
    try:
        sys.exit(main(city))
    except RuntimeError as exc:
        print(f"SKIP: {exc}")
        sys.exit(0)