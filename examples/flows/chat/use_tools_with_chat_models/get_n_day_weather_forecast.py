from promptflow.core import tool


@tool
def get_n_day_weather_forecast(location: str, format: str, num_days: str):
    """Get next num_days weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "60",
        "format": format,
        "forecast": ["rainy"],
        "num_days": num_days,
    }
    return weather_info
