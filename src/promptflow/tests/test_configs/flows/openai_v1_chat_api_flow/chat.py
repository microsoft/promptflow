import os
from openai import AzureOpenAI

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


def create_messages(question, chat_history):
    yield {"role": "system", "content": "You are a helpful assistant."}
    for chat in chat_history:
        yield {"role": "user", "content": chat["inputs"]["question"]}
        yield {"role": "assistant", "content": chat["outputs"]["answer"]}
        yield {"role": "user", "content": question}


@tool
def chat(connection: AzureOpenAIConnection, question: str, chat_history: list) -> str:
    os.environ["AZURE_OPENAI_API_KEY"] = connection.api_key
    os.environ["OPENAI_API_VERSION"] = connection.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = connection.api_base
    client = AzureOpenAI()
    response = client.chat.completions.create(
        model="gpt-35-turbo",
        messages=list(create_messages(question, chat_history))
    )
    return response.choices[0].message.content
