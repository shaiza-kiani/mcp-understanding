from __future__ import annotations

from pydantic import AnyUrl, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    WEATHER_API_KEY: str = Field(..., description="OpenWeatherMap API key")
    OWM_BASE_URL: str = Field("https://api.openweathermap.org", description="OWM base URL")
    OWM_UNITS: str = Field("metric", description="metric/imperial/standard")
    OWM_LANG: str = Field("en", description="language code")


def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as e:
        raise RuntimeError(f"Missing/invalid configuration: {e}") from e
