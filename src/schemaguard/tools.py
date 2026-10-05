import httpx

from .agent import Tool
from .schemas import WeatherToolOutput

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "light rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with heavy hail",
}


def get_weather(city: str) -> dict:
    """Fetch live weather for a city. Returns raw, unvalidated data."""
    geo = httpx.get(
        GEOCODE_URL, params={"name": city, "count": 1}, timeout=10
    )
    geo.raise_for_status()
    results = geo.json().get("results")
    if not results:
        raise ValueError(f"City not found: {city}")
    place = results[0]

    forecast = httpx.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,weather_code",
        },
        timeout=10,
    )
    forecast.raise_for_status()
    current = forecast.json()["current"]

    return {
        "temp_c": current["temperature_2m"],
        "humidity": current["relative_humidity_2m"],
        "sky": WEATHER_CODES.get(current["weather_code"], "unknown"),
    }


def build_weather_tool() -> Tool:
    return Tool(
        name="get_weather",
        description="Get the current live weather for a city.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        func=get_weather,
        output_model=WeatherToolOutput,
    )