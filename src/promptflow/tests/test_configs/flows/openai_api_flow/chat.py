import openai
import litellm
from typing import List

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


def create_messages(question, chat_history):
    yield {"role": "system", "content": "You are a helpful assistant."}
    for chat in chat_history:
        yield {"role": "user", "content": chat["inputs"]["question"]}
        yield {"role": "assistant", "content": chat["outputs"]["answer"]}
        yield {"role": "user", "content": question}


@tool
def chat(connection: AzureOpenAIConnection, question: str, chat_history: List) -> str:
    stream = True
    completion = litellm.completion(
        engine="gpt-35-turbo",
        messages=list(create_messages(question, chat_history)),
        temperature=1.0,
        top_p=1.0,
        n=1,
        stream=stream,
        stop=None,
        max_tokens=16,
        **dict(connection),
    )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    yield getattr(chunk.choices[0]["delta"], "content", "")

        # We must return the generator object, not using yield directly here.
        # Otherwise, the function itself will become a generator, despite whether stream is True or False.
        # return generator()
        return "".join(generator())
    else:
        # chat api may return message with no content.
        return getattr(completion.choices[0].message, "content", "")