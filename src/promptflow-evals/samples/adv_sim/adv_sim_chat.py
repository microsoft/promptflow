# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ContentSafetyChatEvaluator
from promptflow.evals.synthetic import AdversarialScenario, SupportedLanguages, UPIAJailbreakAdversarialSimulator


async def call_local_llama2(messages):
    import requests

    url = "http://localhost:11434/api/chat"
    payload = {"model": "llama2-uncensored", "messages": messages, "stream": False}
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        return "I cannot answer that question"
    r_json = response.json()
    response_content = r_json["message"]
    return response_content["content"]


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
    context = None
    response = await call_local_llama2(messages_list)
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


async def evaluate_chat(azure_ai_project, datafile, eval_name):
    content_safety_evaluator = ContentSafetyChatEvaluator(
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
    simulator = UPIAJailbreakAdversarialSimulator(
        azure_ai_project=azure_ai_project, credential=DefaultAzureCredential()
    )

    outputs = await simulator(
        target=callback,
        scenario=AdversarialScenario.ADVERSARIAL_CONVERSATION,
        max_simulation_results=1,
        max_conversation_turns=4,
        language=SupportedLanguages.Spanish,
    )
    print(json.dumps(outputs, indent=2))
    this_dir = os.path.dirname(__file__)

    upia_jailbreak = outputs["upia_jailbreak"]
    upia_output_file = os.path.join(this_dir, "upia_output_spanish.jsonl")
    with open(upia_output_file, "w") as f:
        f.write(json.dumps({"conversation": upia_jailbreak[0]["messages"]}))
    regular = outputs["regular"]
    regular_output_file = os.path.join(this_dir, "regular_output_spanish.jsonl")
    with open(regular_output_file, "w") as f:
        f.write(json.dumps({"conversation": regular[0]["messages"]}))
    try:
        result = await evaluate_chat(azure_ai_project, datafile=upia_output_file, eval_name="upia_chat_eval_Spanish")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(e)
        import pdb

        pdb.set_trace()
    try:
        result = await evaluate_chat(
            azure_ai_project, datafile=regular_output_file, eval_name="regular_chat_eval_Spanish"
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(e)
        import pdb

        pdb.set_trace()


if __name__ == "__main__":
    os.environ["AZURE_SUBSCRIPTION_ID"] = ""
    os.environ["RESOURCE_GROUP"] = ""
    os.environ["PROJECT_NAME"] = ""
    os.environ["AZURE_OPENAI_API_KEY"] = ""
    os.environ["AZURE_OPENAI_ENDPOINT"] = ""
    os.environ["AZURE_DEPLOYMENT"] = ""

    azure_ai_project = {
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.environ.get("RESOURCE_GROUP"),
        "project_name": os.environ.get("PROJECT_NAME"),
    }

    asyncio.run(main(azure_ai_project=azure_ai_project))
    print("done!")
