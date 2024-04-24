# Using prompty in flex flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Because Prompty can be called as a function, user can use prompty in flex flow.


## Create a flex flow with prompty

prompty
```yaml
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
  question:
    type: string
  chat_history:
    type: list
sample:
  inputs:
    question: What is Prompt flow?
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

entry code of flex flow:
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
        print(result, end="")
```

## Test flex flow with prompty

- Run as normal python file
```batch
python path/to/entry.py
```

- Test flex flow

```bash
pf flow test --flow path/to/flow.flex.yaml --inputs "question=What is ChatGPT?"
```

- Batch run flex flow

```bash
pf run create --flow path/to/flow.flex.yaml --data path/to/data.jsonl --column-mapping question='${data.question}' 
```