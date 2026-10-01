from __future__ import annotations

from pydantic import BaseModel, Field


class Condition(BaseModel):
    id: int
    main: str
    description: str
    icon: str


class Main(BaseModel):
    temp: float
    feels_like: float
    temp_min: float
    temp_max: float
    pressure: int
    humidity: int


class Wind(BaseModel):
    speed: float
    deg: float | None = None


class Rain(BaseModel):
    one_h: float | None = Field(default=None, alias="1h")
    three_h: float | None = Field(default=None, alias="3h")


class Sys(BaseModel):
    country: str | None = None
    sunrise: int | None = None
    sunset: int | None = None


class WeatherResponse(BaseModel):
    city: str
    country: str | None = None
    coordinates: dict[str, float] | None = None
    observed_at: int
    conditions: list[Condition]
    temperature: Main
    wind: Wind
    clouds: dict[str, int] | None = None
    rain: Rain | None = None
    snow: Rain | None = None
    visibility: int | None = None
    humidity: int
    units: str = "metric"