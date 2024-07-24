import os
from pprint import pprint

from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ChatEvaluator

if __name__ == "__main__":
    # Initialize Chat Evaluator

    os.environ["AZURE_OPENAI_API_KEY"] = "<>"
    os.environ["AZURE_OPENAI_API_VERSION"] = "2023-03-15-preview"
    os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4-32k"
    os.environ["AZURE_OPENAI_ENDPOINT"] = "<>"

    # Initialize Project Scope
    project_scope = {
        "subscription_id": "<>",
        "resource_group_name": "<>",
        "project_name": "<>",
    }

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_KEY"),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
    )

    chat_eval = ChatEvaluator(model_config=model_config)

    # Running Chat Evaluator on single input row
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_sample_data.jsonl")
    result = evaluate(
        azure_ai_project=project_scope,
        data=path,
        evaluators={
            "chat": chat_eval,
        },
        evaluator_config={
            "chat": {"conversation": "${data.messages}"},
        },
    )

    pprint(result)
