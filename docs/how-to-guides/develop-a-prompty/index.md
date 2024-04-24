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

Fields in the front matter:

| Field       | Description                                                                             |
|-------------|-----------------------------------------------------------------------------------------|
| name        | The name of the prompt.                                                                 |
| description | A description of the prompt.                                                            |
| model       | Model configuration of prompty, contains connection info and LLM request parameters.    |
| inputs      | Define the inputs received by the prompt template.                                      |
| outputs     | Specify the fields in prompty result. (Only works when response format is json_object.) |
| sample      | A dict or json file of inputs/outputs sample data.                                      |

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
User can override the configuration in the model during load prompty.

::::{tab-set}
:::{tab-item} Azure OpenAI
:sync: Azure OpenAI

```yaml
---
name: Basic Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
    api: chat
    configuration:
      type: azure_openai
      azure_deployment: gpt-35-turbo
      api_key: <api-key>
      api_version: <api-version>
      azure_endpoint: <azure-endpoint>
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
Users can override prompty's configuration and LLM parameters when loading prompty.
Users can also use this format `${env:ENV_NAME}` to pass configuration through environment variables.

#### Override model by dict

```python
from promptflow.core import Prompty

# Load prompty with dict override
override_model = {
    "configuration": {
        "api_key": "${env:AZURE_OPENAI_API_KEY}",
        "api_version": "${env:AZURE_OPENAI_API_VERSION}",
        "azure_endpoint": "${env:AZURE_OPENAI_ENDPOINT}"
    },
    "parameters": {"max_token": 512}
}
prompty = Prompty.load(source="path/to/prompty.prompty", model=override_model)
```

#### Override model by AzureOpenAIModelConfiguration

```python
from promptflow.core import Prompty, AzureOpenAIModelConfiguration

# Load prompty with dict override
configuration = AzureOpenAIModelConfiguration(
    azure_deployment="gpt-3.5-turbo",
    api_key="${env:AZURE_OPENAI_API_KEY}",
    api_version="${env:AZURE_OPENAI_API_VERSION}",
    azure_endpoint="${env:AZURE_OPENAI_ENDPOINT}"
)
override_model = {
    "configuration": configuration,
    "parameters": {"max_token": 512}
}
prompty = Prompty.load(source="path/to/prompty.prompty", model=override_model)
```

:::

:::{tab-item} OpenAI
:sync: OpenAI
```yaml
---
name: Basic Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
    api: chat
    configuration:
      type: openai
      model: gpt-3.5-turbo
      api_key: <api-key>
      base_url: <api_base>
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
Users can override prompty's configuration and LLM parameters when loading prompty.
Users can also use this format `${env:ENV_NAME}` to pass configuration through environment variables.

#### Override model by dict

```python
from promptflow.core import Prompty

# Load prompty with dict override
override_model = {
    "configuration": {
        "api_key": "${env:OPENAI_API_KEY}",
        "base_url": "${env:OPENAI_BASE_URL}",
    },
    "parameters": {"max_token": 512}
}
prompty = Prompty.load(source="path/to/prompty.prompty", model=override_model)
```

#### Override model by OpenAIModelConfiguration

```python
from promptflow.core import Prompty, OpenAIModelConfiguration

# Load prompty with dict override
configuration = OpenAIModelConfiguration(
    model="gpt-35-turbo",
    base_url="${env:OPENAI_BASE_URL}",
    api_key="${env:OPENAI_API_KEY}",
)
override_model = {
    "configuration": configuration,
    "parameters": {"max_token": 512}
}
prompty = Prompty.load(source="path/to/prompty.prompty", model=override_model)
```

:::
::::

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
result = pf.test(flow="path/to/prompty.prompty", inputs="path/to/sample.json")
```

:::
::::

#### Test with interactive mode

Promptflow CLI provides a way to start an interactive chat session for chat flow. Customer can use below command to start an interactive chat session:

```bash
pf flow test --flow path/to/prompty.prompty --interactive
```

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

Terminal outputs:

![prompty_chat.png](../../media/how-to-guides/prompty/prompty_chat.png)

### Batch run prompty

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf run create --flow path/to/prompty.prompty --data path/to/inputs.jsonl
```


:::

:::{tab-item} SDK
:sync: SDK
```python
from promptflow.client import PFClient

pf = PFClient() 
# create run
prompty_run = pf.run(
    flow=r"C:\project\promptflow\src\promptflow\tests\test_configs\prompty\prompty_example.prompty",
    data=r"C:\project\promptflow\src\promptflow\tests\test_configs\datas\prompty_inputs.jsonl",
)
pf.stream(prompty_run)
```

:::
::::

When executing a batch run, promptflow will provide a trace ui to visualize the internal execution details for this run. Learn [more](../tracing/index.md).

```text
Prompt flow service has started...
You can view the traces from local: http://localhost:49240/v1.0/ui/traces/?#run=prompty_variant_0_20240424_152808_282517
[2024-04-24 15:28:12,597][promptflow._sdk._orchestrator.run_submitter][INFO] - Submitting run prompty_variant_0_20240424_152808_282517, log path: .promptflow\.runs\prompty_variant_0_20240424_152808_282517\logs.txt
```