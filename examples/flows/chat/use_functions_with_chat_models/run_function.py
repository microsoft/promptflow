from promptflow import tool
import json


def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return weather_info


def get_n_day_weather_forecast(location, format, num_days):
    """Get next num_days weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "60",
        "format": format,
        "forecast": ["rainy"],
        "num_days": num_days,
    }
    return weather_info


@tool
def run_function(response_message: dict) -> str:
    if "function_call" in response_message:
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])
        print(function_args)
        result = globals()[function_name](**function_args)
    else:
        print("No function call")
        if isinstance(response_message, dict):
            result = response_message["content"]
        else:
            result = response_message
    return result
