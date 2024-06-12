# Using prompty in flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Since Prompty can be called as a function, a user can use prompty in a `flow` which can be a python function or class.
This allows the user to do more customization logic with prompty.


## Consume prompty in code

Example prompty: 

```text
---
name: Stream Chat
description: Chat with stream enabled.
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-35-turbo
  parameters:
    temperature: 0.2
    stream: true

inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
  chat_history:
    type: list
sample:
  first_name: John
  last_name: Doe
  question: What is Prompt flow?
  chat_history: [ { "role": "user", "content": "what's the capital of France?" }, { "role": "assistant", "content": "Paris" } ]
---
system:
You are a helpful assistant.
Here is a chat history you had with the user:
{% for item in chat_history %}
{{item.role}}:
{{item.content}}
{% endfor %}

user:
{{question}}
```

Example python code:
```python
from promptflow.tracing import trace
from promptflow.core import AzureOpenAIModelConfiguration, Prompty


class ChatFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration):
        self.model_config = model_config

    @trace
    def __call__(
        self, question: str = "What is ChatGPT?", chat_history: list = None
    ) -> str:
        """Flow entry function."""

        chat_history = chat_history or []

        prompty = Prompty.load(
            source="path/to/chat.prompty",
            model={"configuration": self.model_config},
        )

        # output is a generator of string as prompty enabled stream parameter
        output = prompty(question=question, chat_history=chat_history)

        return output


if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()
    config = AzureOpenAIModelConfiguration(
        connection="open_ai_connection", azure_deployment="gpt-35-turbo"
    )
    flow = ChatFlow(model_config=config)
    result = flow("What's Azure Machine Learning?", [])

    # print result in stream manner
    for r in result:
        print(r, end="")
```

## Run as normal python file

User can run above code as normal python file.

```batch
python path/to/entry.py
```

## Test the class as a flow

User can also leverage promptflow to test the class as a `flow`.

```bash
pf flow test --flow file:ChatFlow --init init.json --inputs question="What is ChatGPT?"
```

With the `flow` concept, user can further do a rich set of tasks, like:
- Batch run a flow in parallel against multiple lines of data, see [Run and evaluate a flow](../run-and-evaluate-a-flow/index.md).
- Chat with a flow using an UI, see [Chat with a flow](../chat-with-a-flow/index.md).
- Deploy the flow to multiple platforms, see [Deploy a flow](../deploy-a-flow/index.md).

Check the next section to learn more on flow.

