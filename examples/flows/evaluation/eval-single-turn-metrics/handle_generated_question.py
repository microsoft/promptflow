from promptflow.core import tool
import json


@tool
def handle_generated_question(llm_result: str) -> str:
    try:
        response = json.loads(llm_result)
        return response
    except Exception as e:
        print("exception in handle_generated_question: " + str(e))
        print("llm_result: " + llm_result)
        return {"question": "", "noncommittal": True}
