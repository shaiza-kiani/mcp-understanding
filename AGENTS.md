# Project Instructions

## Backend
- Use FastAPI.
- Keep the existing `/weather` endpoint unchanged unless necessary.

## MCP
- Use FastMCP.
- Weather MCP should expose `get_weather(city)`.
- MCP should call the FastAPI backend.
- Do not let OpenCode access the Weather API directly.

## Frontend
- Create a simple weather web interface.
- Allow the user to enter a city.
- Display temperature, condition, and humidity.
- Frontend should communicate with FastAPI.
- Do not put the Weather API key in frontend code.
- Do not create or modify the frontend unless explicitly requested.

## General
- Keep the code simple and beginner-friendly.
- Do not expose API keys.