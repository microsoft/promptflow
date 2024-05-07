from promptflow.core import tool
import json
from get_current_weather import get_current_weather  # noqa: F401
from get_n_day_weather_forecast import get_n_day_weather_forecast  # noqa: F401


@tool
def run_function(response_message: dict) -> str:
    if "tool_calls" in response_message and response_message["tool_calls"]:
        result = []
        tool_calls = response_message["tool_calls"]
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])
            func_res = globals()[function_name](**function_args)
            result.append(func_res)
    else:
        print("No tool call")
        if isinstance(response_message, dict):
            result = response_message.get("content", "")
        else:
            result = response_message
    return result
