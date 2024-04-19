from openai import AzureOpenAI

from promptflow.tracing import trace


@trace
def chat(question: str, stream: bool) -> str:
    clinet = AzureOpenAI()
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": question},
    ]
    completion = clinet.chat.completions.create(
        model="gpt-35-turbo",
        messages=messages,
        temperature=1.0,
        top_p=1.0,
        n=1,
        stream=stream,
        stop=None,
        max_tokens=16
    )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    yield chunk.choices[0].delta.content or ""
        # We must return the generator object, not using yield directly here.
        # Otherwise, the function itself will become a generator, despite whether stream is True or False.
        # return generator()
        return "".join(generator())
    else:
        # chat api may return message with no content.
        return completion.choices[0].message.content or ""
