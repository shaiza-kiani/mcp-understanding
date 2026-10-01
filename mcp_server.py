"""Weather MCP server.

Exposes one tool, `get_weather(city)`, that answers weather questions by calling
the FastAPI backend's existing `/weather` endpoint. This file never talks to
OpenWeatherMap directly, so the API key stays on the server.

Why the FastAPI app is used in-process instead of over HTTP:

Normally you would start the backend (`uvicorn main:app`) and point this server
at `http://localhost:8000`. To avoid needing that second process, we import the
FastAPI `app` object and use an "ASGI transport", which lets `httpx` send
requests straight into the app in memory -- no socket, no extra process.

One catch: FastAPI only creates its OpenWeatherMap client during startup, and
`LifespanManager` is what runs that startup (and the matching shutdown). Without
it, every call would fail with a missing client error.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from asgi_lifespan import LifespanManager
from dotenv import load_dotenv
from fastmcp import FastMCP

# MCP clients start this server with an arbitrary working directory, so the
# project's .env has to be loaded by absolute path before anything reads config.
load_dotenv(Path(__file__).parent / ".env")

from main import app as fastapi_app  # noqa: E402  (must follow load_dotenv)

mcp = FastMCP(name="weather-mcp", version="1.0.0")


@asynccontextmanager
async def weather_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield a client that can call the FastAPI app, startup and shutdown included."""
    async with LifespanManager(fastapi_app):
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://fastapi") as client:
            yield client


def read_error_detail(response: httpx.Response) -> str:
    """Pull a readable message out of a failed response.

    FastAPI reports its own errors as JSON, but a proxy or unhandled crash in
    front of the app can return plain text or HTML, so fall back to the raw body.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("message") or "no detail provided")
    if isinstance(body, list):
        return ", ".join(str(item) for item in body)[:200]
    return "no detail provided"


def trim(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce the backend's full response to the fields worth sending to a model.

    The backend returns wind, clouds, coordinates and timestamps too. Keeping the
    result small matters because every field here is spent context in the caller.
    """
    conditions = payload.get("conditions") or []
    condition = conditions[0].get("description", "unknown") if conditions else "unknown"
    temperature = payload.get("temperature") or {}

    return {
        "city": payload.get("city", "Unknown"),
        "temperature": temperature.get("temp"),
        "feels_like": temperature.get("feels_like"),
        "units": payload.get("units", "metric"),
        "condition": condition,
        "humidity": payload.get("humidity", 0),
    }


@mcp.tool()
async def get_weather(city: str) -> dict[str, Any]:
    """Return the current weather for a city.

    Args:
        city: City name to look up, e.g. "Islamabad" or "Tokyo, JP".
    """
    async with weather_client() as client:
        response = await client.get("/weather", params={"city": city})

        if response.status_code != 200:
            raise ValueError(
                f"Weather lookup failed ({response.status_code}): "
                f"{read_error_detail(response)}"
            )

        return trim(response.json())


if __name__ == "__main__":
    mcp.run()
