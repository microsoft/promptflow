# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import requests
from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ContentSafetyEvaluator
from promptflow.evals.synthetic import AdversarialScenario, SupportedLanguages, UPIAJailbreakAdversarialSimulator

search_documents = []


async def call_local_llama2(user_query: str, context: str = None):
    url = "http://localhost:11434/api/generate"

    prompt = f"""
    You are a helpful AI assistant. You are helping a user with a question. The user asks: "{user_query}".
    I have also found this information that might be helpful to answer the question: "{context}"
    """
    payload = {"model": "llama2-uncensored", "prompt": prompt, "stream": False}
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        return "I cannot answer that question"
    r_json = response.json()
    response_content = r_json["response"]
    return response_content


async def customer_application(user_query: str):
    matching_documents = [doc for doc in search_documents if user_query in doc]
    response = await call_local_llama2(matching_documents)
    return response


async def customer_application_in_red_team_mode(user_query: str, xpia_context: str):
    matching_documents = [doc for doc in search_documents if user_query in doc]
    matching_documents.append(xpia_context)
    response = await call_local_llama2(user_query, matching_documents)
    return response


async def callback(
    messages: List[Dict],
    stream: bool = False,
    session_state: Any = None,  # noqa: ANN401
    context: Optional[Dict[str, Any]] = None,
) -> dict:
    messages_list = messages["messages"]
    # get last message
    latest_message = messages_list[-1]
    query = latest_message["content"]
    context = context["xpia_injection_text"]
    response = await customer_application_in_red_team_mode(query, context)
    # response = "I cannot answer that question"
    # we are formatting the response to follow the openAI chat protocol format
    formatted_response = {
        "content": response,
        "role": "assistant",
        "context": {
            "citations": None,
        },
    }
    messages["messages"].append(formatted_response)
    return {"messages": messages["messages"], "stream": stream, "session_state": session_state, "context": context}


async def evaluate_responses(azure_ai_project, datafile, eval_name):
    content_safety_evaluator = ContentSafetyEvaluator(
        project_scope={
            "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
            "resource_group_name": os.environ.get("RESOURCE_GROUP"),
            "project_name": os.environ.get("PROJECT_NAME"),
        }
    )
    try:
        result = evaluate(
            evaluation_name=eval_name,
            data=datafile,
            evaluators={
                "content_safety": content_safety_evaluator,
            },
            azure_ai_project=azure_ai_project,
        )
        print(result["studio_url"])
        return result
    except Exception as e:
        print(e)
        import pdb

        pdb.set_trace()


async def main(azure_ai_project):
    from promptflow.evals.synthetic import XPIAJailbreakAdversarialSimulator

    XPIAsimulator = XPIAJailbreakAdversarialSimulator(azure_ai_project=azure_ai_project)

    outputs = await XPIAsimulator(
        target=callback, max_simulation_results=10  # required, callback function to simulate against  # optional
    )

    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    azure_ai_project = {
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.environ.get("RESOURCE_GROUP"),
        "project_name": os.environ.get("PROJECT_NAME"),
    }

    asyncio.run(main(azure_ai_project=azure_ai_project))
    print("done!")
