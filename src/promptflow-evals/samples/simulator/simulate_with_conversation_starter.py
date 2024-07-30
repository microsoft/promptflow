# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import wikipedia
from azure.identity import DefaultAzureCredential

from promptflow.client import load_flow
from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.evals.synthetic import Simulator

wiki_search_term = "Leonardo da vinci"
wiki_title = wikipedia.search(wiki_search_term)[0]
wiki_page = wikipedia.page(wiki_title)
text = wiki_page.summary[:5000]


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
    # call your endpoint or ai application here
    current_dir = os.path.dirname(__file__)
    prompty_path = os.path.join(current_dir, "application.prompty")
    _flow = load_flow(source=prompty_path, model={"configuration": azure_ai_project})
    response = _flow(query=query, context=context, conversation_history=messages_list)
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


async def main(model_config, azure_ai_project):
    conversation_turns = [
        # simulation 1
        [
            "Hello, how are you?",  # simulator conversation starter (turn 1)
            f"I want to learn more about Paris"  # conversation turn 2,
            f"Thanks for helping me. What else should I know about Paris for my project",  # conversation turn 3
        ],
        # simulation 2
        [
            "Hey, I really need your help to finish my homework.",
            f"I need to write an essay about Paris",
            f"Thanks, can you rephrase your last response to help me understand it better?",
        ],
    ]
    simulator = Simulator(azure_ai_project=azure_ai_project, credential=DefaultAzureCredential())
    outputs = await simulator(target=callback, conversation_turns=conversation_turns)
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    os.environ["AZURE_SUBSCRIPTION_ID"] = ""
    os.environ["RESOURCE_GROUP"] = ""
    os.environ["PROJECT_NAME"] = ""
    os.environ["AZURE_OPENAI_API_KEY"] = ""
    os.environ["AZURE_OPENAI_ENDPOINT"] = ""
    os.environ["AZURE_DEPLOYMENT"] = ""
    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
    )
    azure_ai_project = {
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.environ.get("RESOURCE_GROUP"),
        "project_name": os.environ.get("PROJECT_NAME"),
    }

    asyncio.run(main(model_config=model_config, azure_ai_project=azure_ai_project))
    print("done!")
