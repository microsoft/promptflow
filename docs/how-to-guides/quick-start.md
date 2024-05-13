# Quick start

This guide will walk you through the fist step using of prompt flow code-first experience.

**Prerequisite** - To make the most of this tutorial, you'll need:
- Know how to program with Python :)

**Learning Objectives** - Upon completing this tutorial, you should learn how to:
- Setup your python environment to run prompt flow
- Create a flow using a prompt and python function
- Test the flow using your favorite experience: CLI, SDK or UI.

## Installation

Install promptflow package to start.
```sh
pip install promptflow
```

Learn more on installation topic. TODO

## Create your first flow

### Model a LLM call with a prompty

Create a Prompty file to help you trigger one LLM call. 

```md
---
name: Minimal Chat
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-35-turbo
  parameters:
    temperature: 0.2
    max_tokens: 1024
sample:
  question: "What is Prompt flow?"
---

system:
You are a helpful assistant.

user:
{{question}}
```

Prompty is a markdown file. The front matter structured in `YAML`, encapsulates a series of metadata fields pivotal for defining the model’s configuration and the inputs for the prompty. After this front matter is the prompt template, articulated in the `Jinja` format.
See more details in [Develop a prompty](./develop-a-prompty/index.md). 

### Create a flow
Create a python function which is the entry of a `flow`. 

```python
import os

from dotenv import load_dotenv
from pathlib import Path
from promptflow.tracing import trace
from promptflow.core import Prompty

BASE_DIR = Path(__file__).absolute().parent

@trace
def chat(question: str = "What's the capital of France?") -> str:
    """Flow entry function."""

    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        # load environment variables from .env file
        load_dotenv()

    prompty = Prompty.load(source=BASE_DIR / "chat.prompty")
    # trigger a llm call with the prompty obj
    output = prompty(question=question)
    return output
```

Flow can be a python function or class or a yaml file describe a DAG which encapsulate your LLM application logic. Learn more on the [flow concept](../concepts/concept-flows.md).

## Test the flow

Test the flow with your favorite experience: CLI, SDK or UI.

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

`pf` is the CLI command you get when install `promptflow` package. Learn more on features of `pf` CLI in[reference doc](https://microsoft.github.io/promptflow/reference/pf-command-reference.html).

```sh
pf flow test --flow flow:chat --inputs question="What's the capital of France?"
```

You will get some output like below in terminal.
```
```

TODO add screenshot on Trace UI.

:::

:::{tab-item} SDK
:sync: SDK

Call the chat function with your question. Assume you have a `flow.py` file with below content.
```python
if __name__ == "__main__":
    from promptflow.tracing import start_trace

    start_trace()

    result = chat("What's the capital of France?")
    print(result)
```

Run you script with `python flow.py`, and you will get some outputs like below:
```

```

TODO add screenshot on Trace UI.
:::

:::{tab-item} UI
:sync: VS Code Extension

start test in chat ui

```sh
pf flow test --flow flow:chat --ui 
```

TODO add screenshot on Chat UI.

See more details of this topic in [Chat with a flow](./chat-with-a-flow/index.md).

:::

::::


## Next steps

Learn more on how to:
- [Develop a prompty](./develop-a-prompty/index.md): details on how to develop prompty.
- [Develop a flow](./develop-a-flex-flow/index.md): details on how to develop a flow by using a Python function or class.
- [Develop a flow with DAG](./develop-a-dag-flow/index.md): details on how to develop a flow by using friendly DAG UI.

And you can also check our [Tutorials](https://microsoft.github.io/promptflow/tutorials/index.html), especially:
- [Tutorial: Chat with PDF](https://microsoft.github.io/promptflow/tutorials/chat-with-pdf.html): An end-to-end tutorial on how to build a high quality chat application with prompt flow, including flow development and evaluation with metrics.

```{toctree}
:caption: Installation
:maxdepth: 1
installation/index
```