# Prompty

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Promptflow provides the `prompty` feature to provide customers with a simple way to develop prompt template.

## Create a prompty
In promptflow, a file with a `.prompty` extension will be treated as a prompty.

### Prompty specification
The prompty asset is a markdown file with a modified front matter. 
The front matter is in yaml format that contains a number of metadata fields which defines model configuration and expected inputs of the prompty.
```yaml
---
name: Basic Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
    api: chat
    configuration:
      type: azure_openai
      azure_deployment: gpt-35-turbo
      connection: azure_open_ai_connection
    parameters:
      max_tokens: 128
      temperature: 0.2
inputs:
  first_name:
    type: string
    default: John
  last_name:
    type: string
    default: Doh
  question:
    type: string
---
system:
You are an AI assistant who helps people find information.
As the assistant, you answer questions briefly, succinctly,
and in a personable manner using markdown and even add some personal flair with appropriate emojis.

# Safety
- You **should always** reference factual statements to search results based on [relevant documents]
- Search results based on [relevant documents] may be incomplete or irrelevant. You do not make assumptions
# Customer
You are helping {{first_name}} {{last_name}} to find answers to their questions.
Use their name to address them in your responses.

user:
{{question}}
```

## Load a prompty

TODO



## Execute a prompty

Prompty can be executed in these ways to meet the needs of customers in different scenarios.

### Prompty as a call
After the customer loads the prompty, the loaded prompty object can be called directly as a function. The return value is the content of the LLM response.
```python
from promptflow.core import Prompty

prompty_obj = Prompty.load(source="path/to/prompty.prompty")
result = prompty_obj(first_name="John", last_name="Doh", question="What is the capital of France?")
```

### Test prompty

#### Test as a flow

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
# Test prompty with default inputs
pf flow test --flow path/to/prompty.prompty

# Test prompty with specified inputs
pf flow test --flow path/to/prompty.prompty --inputs first_name=John last_name=Doh question="What is the capital of France?"

# Test prompty with sample file
pf flow test --flow path/to/prompty.prompty --inputs path/to/sample.json
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from promptflow.client import PFClient

pf = PFClient()

# Test prompty with specified inputs
result = pf.test(flow="path/to/prompty.prompty", inputs={"first_name": "John", "last_name": "Doh", "question": "What is the capital of France?"})

# Test prompty with sample file
result = pf.test(flow="path/to/prompty.prompty", inputs="path/to/sample.json"
```

:::
::::

#### Test with interactive mode

Promptflow CLI provides a way to start an interactive chat session for chat flow. Customer can use below command to start an interactive chat session:

```yaml
---
name: Basic Prompt With Chat History
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
    api: chat
    configuration:
      type: azure_open_ai
      azure_deployment: gpt-35-turbo
      connection: azure_open_ai_connection

    parameters:
      max_tokens: 128
      temperature: 0.2
inputs:
  first_name:
    type: string
    default: John
  last_name:
    type: string
    default: Doh
  question:
    type: string
    is_chat_input: true
  chat_history:
    is_chat_history: true
    type: list
---
system:
You are an AI assistant who helps people find information.
As the assistant, you answer questions briefly, succinctly,
and in a personable manner using markdown and even add some personal flair with appropriate emojis.

# Safety
- You **should always** reference factual statements to search results based on [relevant documents]
- Search results based on [relevant documents] may be incomplete or irrelevant. You do not make assumptions
# Customer
You are helping {{first_name}} {{last_name}} to find answers to their questions.
Use their name to address them in your responses.

Here is a chat history you had with the user:
{% for item in chat_history %}
   {{item.role}}: {{item.content}}
{% endfor %}

user:
{{question}}
```

```bash
pf flow test --flow path/to/prompty.prompty --interactive
```

![prompty_chat.png](../../media/how-to-guides/prompty/prompty_chat.png)

### Batch run prompty

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf run create --flow path/to/prompty.prompty --data path/to/inputs.jsonl
```

```text
Prompt flow service has started...
You can view the traces from local: http://localhost:49240/v1.0/ui/traces/?#run=prompty_variant_0_20240424_152808_282517
[2024-04-24 15:28:12,597][promptflow._sdk._orchestrator.run_submitter][INFO] - Submitting run prompty_variant_0_20240424_152808_282517, log path: C:\Users\zhrua\.promptflow\.runs\prompty_variant_0_20240424_152808_282517\logs.txt
{
    "name": "prompty_variant_0_20240424_152808_282517",
    "created_on": "2024-04-24T15:28:08.282517",
    "status": "Completed",
    "display_name": "prompty_variant_0_20240424_152808_282517",
    "description": null,
    "tags": null,
    "properties": {
        "flow_path": "C:/project/promptflow/src/promptflow/tests/test_configs/prompty/prompty_example.prompty",
        "output_path": "C:/Users/zhrua/.promptflow/.runs/prompty_variant_0_20240424_152808_282517",
        "system_metrics": {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "duration": 12.031866
        }
    },
    "flow_name": "prompty_example",
    "data": "C:/project/promptflow/src/promptflow/tests/test_configs/datas/prompty_inputs.jsonl",
    "output": "C:/Users/zhrua/.promptflow/.runs/prompty_variant_0_20240424_152808_282517/flow_outputs"
}

```


:::

:::{tab-item} SDK
:sync: SDK
```python
from promptflow.client import PFClient

pf = PFClient() 
# create run
base_run = pf.run(
    flow="path/to/prompty.prompty",
    data="path/to/inputs.jsonl",
)
```

:::
::::