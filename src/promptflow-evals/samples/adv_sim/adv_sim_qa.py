# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ContentSafetyEvaluator
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
    simulator = UPIAJailbreakAdversarialSimulator(
        azure_ai_project=azure_ai_project, credential=DefaultAzureCredential()
    )

    outputs = await simulator(
        target=callback,
        scenario=AdversarialScenario.ADVERSARIAL_QA,
        max_simulation_results=1,
        language=SupportedLanguages.Spanish,
    )
    print(json.dumps(outputs, indent=2))
    this_dir = os.path.dirname(__file__)

    upia_jailbreak = outputs["upia_jailbreak"]
    upia_output_file = os.path.join(this_dir, "upia_output_fr.jsonl")
    with open(upia_output_file, "w") as f:
        f.write(upia_jailbreak.to_eval_qa_json_lines())
    regular = outputs["regular"]
    regular_output_file = os.path.join(this_dir, "regular_output_fr.jsonl")
    with open(regular_output_file, "w") as f:
        f.write(regular.to_eval_qa_json_lines())
    # run QA eval on the output file
    try:
        result = await evaluate_responses(azure_ai_project, datafile=upia_output_file, eval_name="upia_eval_fr")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(e)
        import pdb

        pdb.set_trace()

    try:
        result = await evaluate_responses(azure_ai_project, datafile=regular_output_file, eval_name="regular_eval_fr")
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
