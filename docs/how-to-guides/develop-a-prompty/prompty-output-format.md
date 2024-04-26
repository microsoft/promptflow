# Prompty output format

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

In this doc, you will learn:
- Understand how to handle output format of prompty like: `text`, `json_object`.
- Understand how to consume **stream** output of prompty

## Formatting prompty output

### Text output

By default, prompty returns the message from the first choice in the response. Below is an example of how to format a prompty for text output:

```yaml
---
name: Text Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
  api: chat
  configuration:
    type: azure_openai
    connection: open_ai_connection
    azure_deployment: gpt-35-turbo-0125
  parameters:
    max_tokens: 128
    temperature: 0.2
inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
sample:
  first_name: John
  last_name: Doe
  question: what is the meaning of life?
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

The output of the prompty is a string content, as shown in the example below:

```text
Ah, the age-old question about the meaning of life! 🌍🤔 The meaning of life is a deeply philosophical and subjective topic. Different people have different perspectives on it. Some believe that the meaning of life is to seek happiness and fulfillment, while others find meaning in personal relationships, accomplishments, or spiritual beliefs. Ultimately, it's up to each individual to explore and discover their own purpose and meaning in life. 🌟
```

### Json object output
Prompty can return the content of the first choice as a dictionary object when the following conditions are met:
- The `response_format` is defined as `type: json_object` in the parameters
- The template specifies the JSON format for the return value.

**Note**: `json_object` response_format is compatible with `GPT-4 Turbo` and all GPT-3.5 Turbo models newer than `gpt-3.5-turbo-1106`. For more details, refer to this [document](https://platform.openai.com/docs/api-reference/chat/create#chat-create-response_format).

Here’s how to configure a prompty for JSON object output:
```yaml
---
name: Json Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-35-turbo-0125
    connection: open_ai_connection
  parameters:
    max_tokens: 128
    temperature: 0.2
    response_format:
      type: json_object
inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
sample:
  first_name: John
  last_name: Doe
  question: what is the meaning of life?
---
system:
You are an AI assistant who helps people find information.
As the assistant, you answer questions briefly, succinctly. Your structured response. Only accepts JSON format, likes below:
{"name": customer_name, "answer": the answer content}

# Customer
You are helping {{first_name}} {{last_name}} to find answers to their questions.
Use their name to address them in your responses.

user:
{{question}}
```
The output of the prompty is a JSON object containing the content of the first choice:
```json
{
    "name": "John",
    "answer": "The meaning of life is a philosophical question that varies depending on individual beliefs and perspectives."
}
```

Users can also specify the fields to be returned by configuring the output section:

```yaml
---
name: Json Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
  api: chat
  configuration:
    type: azure_openai
    azure_deployment: gpt-35-turbo-0125
    connection: open_ai_connection
  parameters:
    max_tokens: 128
    temperature: 0.2
    response_format:
      type: json_object
inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
outputs:
  answer:
    type: string
sample:
  first_name: John
  last_name: Doe
  question: what is the meaning of life?
---
system:
You are an AI assistant who helps people find information.
As the assistant, you answer questions briefly, succinctly. Your structured response. Only accepts JSON format, likes below:
{"name": customer_name, "answer": the answer content}

# Customer
You are helping {{first_name}} {{last_name}} to find answers to their questions.
Use their name to address them in your responses.

user:
{{question}}
```
Prompty will then return the outputs as specified by the user:
```json
{
  "answer": "The meaning of life is a philosophical question that varies depending on individual beliefs and perspectives."
}
```

### All choices
In certain scenarios, users may require access to the original response from the language model (LLM) for further processing. This can be achieved by setting `response=all`, which allows retrieval of the original LLM response. For detailed information, please refer to the [LLM response](https://platform.openai.com/docs/api-reference/chat/object).

```yaml
---
name: All Choices Text Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
  api: chat
  configuration:
    type: azure_openai
    connection: open_ai_connection
    azure_deployment: gpt-35-turbo-0125
  parameters:
    max_tokens: 128
    temperature: 0.2
    n: 3
  response: all
inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
sample:
  first_name: John
  last_name: Doe
  question: what is the meaning of life?
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

### Streaming output
For prompty configurations where the response_format is `text`, setting `stream=true` in the parameters will result in the Promptflow SDK returning a generator. Each item from the generator represents the content of a chunk.

Here’s how to configure a prompty for streaming text output:
```yaml
---
name: Stream Mode Text Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
  api: chat
  configuration:
    type: azure_openai
    connection: open_ai_connection
    azure_deployment: gpt-35-turbo-0125
  parameters:
    max_tokens: 512
    temperature: 0.2
    stream: true
inputs:
  first_name:
    type: string
  last_name:
    type: string
  question:
    type: string
sample:
  first_name: John
  last_name: Doe
  question: What's the steps to get rich?
---
system:
You are an AI assistant who helps people find information.
and in a personable manner using markdown and even add some personal flair with appropriate emojis.

# Safety
- You **should always** reference factual statements to search results based on [relevant documents]
- Search results based on [relevant documents] may be incomplete or irrelevant. You do not make assumptions
# Customer
You are helping user to find answers to their questions.

user:
{{question}}
```
To retrieve elements from the generator results, use the following Python code:
```python
from promptflow.core import Prompty

# load prompty as a flow
prompty_func = Prompty.load("stream_output.prompty")
# execute the flow as function
question = "What's the steps to get rich?"
result = prompty_func(first_name="John", last_name="Doh", question=question)
# Type of the result is generator
for item in result:
    print(item, end="")
```
