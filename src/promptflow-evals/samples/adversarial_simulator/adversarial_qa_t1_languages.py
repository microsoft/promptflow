# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator, SupportedLanguages


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
    # call your endpoint to get the response
    response = "I cannot answer that question"

    # we are formatting the response to follow the openAI chat protocol format
    formatted_response = {
        "content": query,
        "role": "assistant",
        "context": {
            "citations": None,
        },
    }
    messages["messages"].append(formatted_response)
    return {"messages": messages["messages"], "stream": stream, "session_state": session_state, "context": context}


async def main(azure_ai_project):
    simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=DefaultAzureCredential())
    outputs = await simulator(
        target=callback,
        scenario=AdversarialScenario.ADVERSARIAL_CONVERSATION,
        max_simulation_results=5,
        max_conversation_turns=3,
        language=SupportedLanguages.French,
    )
    print(json.dumps(outputs, indent=2))
    import pdb

    pdb.set_trace()


if __name__ == "__main__":

    azure_ai_project = {
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.environ.get("RESOURCE_GROUP"),
        "project_name": os.environ.get("PROJECT_NAME"),
    }

    asyncio.run(main(azure_ai_project=azure_ai_project))
    print("done!")
