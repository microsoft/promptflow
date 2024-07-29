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
from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import FluencyEvaluator, GroundednessEvaluator, RelevanceEvaluator
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


async def evaluate_responses(model_config, azure_ai_project):
    relevance_evaluator = RelevanceEvaluator(model_config)
    groundedness_evaluator = GroundednessEvaluator(model_config)
    fluency_evaluator = FluencyEvaluator(model_config)
    current_dir = os.path.dirname(__file__)
    output_file_path = os.path.join(current_dir, "output.jsonl")
    try:
        result = evaluate(
            evaluation_name="task_simulator_eval",
            data=output_file_path,
            evaluators={
                "relevance": relevance_evaluator,
                "groundedness": groundedness_evaluator,
                "fluency": fluency_evaluator,
            },
            # evaluator_config={
            #     "default": {
            #         "ground_truth": "${data.context}",
            #         "context": "${data.context}",
            #     }
            # },
            azure_ai_project=azure_ai_project,
        )
        print(result["studio_url"])
        return result
    except Exception as e:
        print(e)


async def main(model_config, azure_ai_project):
    current_dir = os.path.dirname(__file__)
    query_response_prompty_override = os.path.join(current_dir, "query_generator_long_answer.prompty")
    simulator = Simulator(azure_ai_project=azure_ai_project, credential=DefaultAzureCredential())
    outputs = await simulator(
        target=callback,
        text=text,
        num_queries=4,
        max_conversation_turns=2,
        query_response_generating_prompty=query_response_prompty_override,
        user_persona=[
            f"I am a student and I want to learn more about {wiki_search_term}",
            f"I am a teacher and I want to teach my students about {wiki_search_term}",
            f"I am a researcher and I want to do a detailed research on {wiki_search_term}",
            f"I am a statistician and I want to do a detailed table of factual data concerning {wiki_search_term}",
        ],
    )

    for output in outputs:
        with open("output.jsonl", "a") as f:
            f.write(output.to_eval_qa_json_lines())

        # run eval on the output file
    try:
        result = await evaluate_responses(model_config, azure_ai_project)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(e)


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
