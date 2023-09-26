import openai

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def completion(connection: AzureOpenAIConnection, prompt: str) -> str:
    stream = True
    completion = openai.Completion.create(
        prompt=prompt,
        engine="text-davinci-003",
        max_tokens=256,
        temperature=0.8,
        top_p=1.0,
        n=1,
        stream=stream,
        stop=None,
        **dict(connection),
    )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    yield getattr(chunk.choices[0], "text", "")

        return "".join(generator())
    else:
        return getattr(completion.choices[0], "text", "")
