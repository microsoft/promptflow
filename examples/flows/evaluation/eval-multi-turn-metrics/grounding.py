from typing import Union
from statistics import mean
from promptflow.core import tool
from promptflow.tools.aoai import chat as aoai_chat
from promptflow.tools.openai import chat as openai_chat
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def grounding(connection: Union[AzureOpenAIConnection, OpenAIConnection],
              chat_history: list,
              prompt: str,
              model_or_deployment_name: str = "") -> str:
    score = []
    for item in chat_history:
        prompt_with_context = prompt.replace("{context}", "{{context}}")
        prompt_with_all = prompt_with_context.replace("{answer}", "{{answer}}")
        if isinstance(connection, AzureOpenAIConnection):
            try:
                response = aoai_chat(
                    connection=connection,
                    prompt=prompt_with_all,
                    deployment_name=model_or_deployment_name,
                    context=item["outputs"]["context"],
                    answer=item["outputs"]["answer"])
                print(response)
                score.append(int(response))
            except Exception as e:
                if "The API deployment for this resource does not exist" in str(e):
                    raise Exception(
                        "Please fill in the deployment name of your Azure OpenAI resource gpt-4 model.")

        elif isinstance(connection, OpenAIConnection):
            response = openai_chat(
                connection=connection,
                prompt=prompt_with_all,
                model=model_or_deployment_name,
                context=item["outputs"]["context"],
                answer=item["outputs"]["answer"])
            score.append(int(response))
        else:
            raise ValueError("Connection must be an instance of AzureOpenAIConnection or OpenAIConnection")
    print(score)
    return mean(score)
