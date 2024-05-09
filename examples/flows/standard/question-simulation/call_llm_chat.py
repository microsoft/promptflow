from promptflow.core import tool
from typing import Union
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from openai import AzureOpenAI as AzureOpenAIClient
from openai import OpenAI as OpenAIClient
from promptflow.tools.common import parse_chat


def parse_questions(completion: str) -> list:
    questions = []

    for item in completion.choices:
        response = getattr(item.message, "content", "")
        print(response)
        questions.append(response)
    return questions


@tool
def call_llm_chat(
    connection: Union[AzureOpenAIConnection, OpenAIConnection],
    prompt: str,
    question_count: int,
    deployment_name_or_model: str,
    stop: list = [],
) -> str:

    messages = parse_chat(prompt)
    params = {
                "model": deployment_name_or_model,
                "messages": messages,
                "temperature": 1.0,
                "top_p": 1.0,
                "stream": False,
                "stop": stop if stop else None,
                "presence_penalty": 0.8,
                "frequency_penalty": 0.8,
                "max_tokens": None,
                "n": question_count
            }
    if isinstance(connection, AzureOpenAIConnection):
        client = AzureOpenAIClient(api_key=connection.api_key,
                                   api_version=connection.api_version,
                                   azure_endpoint=connection.api_base)
    elif isinstance(connection, OpenAIConnection):
        client = OpenAIClient(api_key=connection.api_key,
                              organization=connection.organization,
                              base_url=connection.base_url)
    else:
        raise ValueError("Unsupported connection type")

    completion = client.chat.completions.create(**params)
    print(completion)
    questions = parse_questions(completion)

    return "\n".join(questions)
