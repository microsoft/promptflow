from promptflow.core import tool
import json
import numpy as np


@tool
def calculate(llm_result: str) -> str:
    try:
        score = 1
        response = json.loads(llm_result)
        if response:
            result = response.get("result", "")
            print(result)
            if result:
                response = [
                    # Also handle 'attribited' here since llm tool will return 'attribited'
                    # instead of 'attributed' in its' response
                    int(item.get("attributed", "").lower() == "yes" or item.get("attribited", "").lower() == "yes")
                    if item.get("attributed") or item.get("attribited")
                    else np.nan
                    for item in result
                ]
                denom = len(response)
                print(response)
                print(denom)
                numerator = sum(response)
                score = 5 * numerator / denom
        return score if score >= 1 else 1
    except Exception as e:
        print("exception in calculate_context_recall: " + str(e))
        print("llm_result: " + llm_result)
        return np.nan
