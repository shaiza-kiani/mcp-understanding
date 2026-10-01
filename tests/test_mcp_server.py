"""MCP layer tests.

These run against the real FastAPI app and the real OpenWeatherMap API, so they
need a genuine key in .env. The conftest autouse fixture injects a fake key for
the FastAPI unit tests, which is cleared here.
"""

from __future__ import annotations

import inspect

import pytest
from fastmcp import Client

import main
import mcp_server


@pytest.fixture(autouse=True)
def real_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)


@pytest.fixture
async def client():
    async with Client(mcp_server.mcp) as c:
        yield c


async def test_tool_is_registered(client: Client) -> None:
    tools = await client.list_tools()
    tool = next(t for t in tools if t.name == "get_weather")
    assert "weather" in (tool.description or "").lower()


async def test_get_weather_returns_trimmed_payload(client: Client) -> None:
    result = await client.call_tool("get_weather", {"city": "Islamabad"})
    assert result.data["city"] == "Islamabad"
    assert result.data["units"] == "metric"
    assert isinstance(result.data["temperature"], float)
    assert isinstance(result.data["humidity"], int)
    assert result.data["condition"]


async def test_payload_is_trimmed(client: Client) -> None:
    """Only the agreed fields should reach the caller; the rest is dead weight."""
    result = await client.call_tool("get_weather", {"city": "Islamabad"})
    assert set(result.data) == {
        "city",
        "temperature",
        "feels_like",
        "units",
        "condition",
        "humidity",
    }
    for dropped in ("coordinates", "observed_at", "wind", "clouds", "visibility", "conditions"):
        assert dropped not in result.data


async def test_unknown_city_raises(client: Client) -> None:
    with pytest.raises(Exception, match="Weather lookup failed"):
        await client.call_tool("get_weather", {"city": "Atlantisxyz999"})


# --- error handling ---------------------------------------------------------


def test_read_error_detail_from_json() -> None:
    import httpx

    response = httpx.Response(404, json={"detail": "City not found: Atlantis"})
    assert mcp_server.read_error_detail(response) == "City not found: Atlantis"


def test_read_error_detail_from_html_does_not_raise() -> None:
    """Regression: a non-JSON error body used to raise JSONDecodeError."""
    import httpx

    response = httpx.Response(502, text="<html>Bad Gateway</html>")
    detail = mcp_server.read_error_detail(response)
    assert "Bad Gateway" in detail


def test_read_error_detail_from_json_list() -> None:
    import httpx

    response = httpx.Response(500, json=["boom"])
    assert mcp_server.read_error_detail(response) == "boom"


def test_read_error_detail_without_detail_key() -> None:
    import httpx

    response = httpx.Response(500, json={"message": "Internal Server Error"})
    assert mcp_server.read_error_detail(response) == "Internal Server Error"


# --- trimming ---------------------------------------------------------------


def test_trim_handles_missing_blocks() -> None:
    trimmed = mcp_server.trim({})
    assert trimmed["city"] == "Unknown"
    assert trimmed["condition"] == "unknown"
    assert trimmed["temperature"] is None
    assert trimmed["humidity"] == 0


def test_trim_handles_empty_conditions() -> None:
    trimmed = mcp_server.trim({"conditions": [], "city": "Nowhere"})
    assert trimmed["condition"] == "unknown"


async def test_fastapi_source_unmodified() -> None:
    """Guard the constraint: the MCP layer must not have altered the FastAPI module."""
    source = inspect.getsource(main)
    assert "fastmcp" not in source
    assert "mcp_server" not in source
    assert "/weather" in source