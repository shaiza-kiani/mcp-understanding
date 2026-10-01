from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import AfterValidator, ValidationError

from config import Settings, get_settings
from owm import (
    OpenWeatherClient,
    WeatherAPIError,
    WeatherAuthError,
    WeatherNotFoundError,
    to_weather_response,
)
from schemas import WeatherResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.client = OpenWeatherClient(
        api_key=settings.WEATHER_API_KEY,
        base_url=settings.OWM_BASE_URL,
        units=settings.OWM_UNITS,
        lang=settings.OWM_LANG,
    )
    yield
    await app.state.client.aclose()


app = FastAPI(title="Weather API", version="1.0.0", lifespan=lifespan)


def get_client(request: Request) -> OpenWeatherClient:
    return request.app.state.client


def get_units(request: Request) -> str:
    return request.app.state.settings.OWM_UNITS


def _clean_city(value: str) -> str:
    """Strip padding and reject blank input.

    ``Query(min_length=1)`` counts characters, so ``"   "`` would otherwise be
    forwarded to the provider as a useless query.
    """
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("city must not be blank")
    return cleaned


ClientDep = Annotated[OpenWeatherClient, Depends(get_client)]
UnitsDep = Annotated[str, Depends(get_units)]
CityParam = Annotated[
    str, Query(min_length=1, max_length=100, examples=["London"]), AfterValidator(_clean_city)
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/weather", response_model=WeatherResponse, response_model_exclude_none=True)
async def get_weather(
    city: CityParam,
    client: ClientDep,
    units: UnitsDep,
) -> WeatherResponse:
    try:
        payload = await client.get_current(city)
    except WeatherNotFoundError:
        raise HTTPException(status_code=404, detail=f"City not found: {city}")
    except WeatherAuthError:
        raise HTTPException(status_code=500, detail="Server API key is invalid")
    except WeatherAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        return WeatherResponse.model_validate(to_weather_response(payload, units))
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"Unexpected provider payload: {exc.errors()[:3]}"
        )