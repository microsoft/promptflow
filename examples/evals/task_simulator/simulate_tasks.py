# flake8: noqa

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from promptflow.client import load_flow
from promptflow.evals.synthetic import TaskSimulator

azure_ai_project = {
    "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
    "resource_group_name": os.environ.get("RESOURCE_GROUP"),
    "project_name": os.environ.get("PROJECT_NAME"),
    "credential": DefaultAzureCredential(),
}

import wikipedia

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


async def main():
    current_dir = os.path.dirname(__file__)
    query_response_prompty_override = os.path.join(current_dir, "query_generator_long_answer.prompty")
    simulator = TaskSimulator(azure_ai_project=azure_ai_project, credential=DefaultAzureCredential())
    outputs = await simulator(
        target=callback,
        text=text,
        num_queries=4,
        max_conversation_turns=4,
        query_response_generating_prompty=query_response_prompty_override,
        user_persona=[
            f"I am a student and I want to learn more about {wiki_search_term}",
            f"I am a teacher and I want to teach my students about {wiki_search_term}",
            f"I am a researcher and I want to do a detailed research on {wiki_search_term}",
            f"I am a statistician and I want to do a detailed table of factual data concerning {wiki_search_term}",
        ],
    )
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    os.environ["AZURE_SUBSCRIPTION_ID"] = ""
    os.environ["RESOURCE_GROUP"] = ""
    os.environ["PROJECT_NAME"] = ""
    os.environ["AZURE_OPENAI_API_KEY"] = ""
    os.environ["AZURE_OPENAI_ENDPOINT"] = ""
    os.environ["AZURE_DEPLOYMENT"] = ""

    asyncio.run(main())
    print("done!")
