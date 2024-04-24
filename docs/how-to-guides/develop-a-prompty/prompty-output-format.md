# Prompty output format

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

In this doc, you will learn:
- Understand how to handle output format of prompty like: text, json_object.
- Understand how to consume stream output of prompty

## Format prompty output

### Text output
By default, the prompty returns the message of first choices.

```yaml
---
name: Text Format Prompt
description: A basic prompt that uses the GPT-3 chat API to answer questions
model:
    api: chat
    configuration:
      type: azure_openai
      connection: <connection_name>
      azure_deployment: gpt-35-turbo-0125
    parameters:
      max_tokens: 128
      temperature: 0.2
sample:
  inputs:
    first_name: John
    last_name: Doh
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
The return value of the prompty is a string content.
```text
Ah, the age-old question about the meaning of life! 🌍🤔 The meaning of life is a deeply philosophical and subjective topic. Different people have different perspectives on it. Some believe that the meaning of life is to seek happiness and fulfillment, while others find meaning in personal relationships, accomplishments, or spiritual beliefs. Ultimately, it's up to each individual to explore and discover their own purpose and meaning in life. 🌟
```

### Json object output
When the user meets the following conditions, prompty returns content of first choices as a dict.
- Define response_format to type: json_object in parameters
- Specify the return json format in template.

**Note**: response_format is compatible with `GPT-4 Turbo` and all GPT-3.5 Turbo models newer than `gpt-3.5-turbo-1106`. For more details, refer to this [document](https://platform.openai.com/docs/api-reference/chat/create#chat-create-response_format).

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
sample:
  inputs:
    first_name: John
    last_name: Doh
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
The return value of the prompty is a json object of first choice content.
```json
{
    "name": "John",
    "answer": "The meaning of life is a philosophical question that varies depending on individual beliefs and perspectives."
}
```

Users can also specify the returned fields by configuring output.
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
sample:
  inputs:
    first_name: John
    last_name: Doh
    question: what is the meaning of life?
  outputs:
    answer: The meaning of life is a philosophical question
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
Prompty will eventually return the user-specified outputs.
```json
{
  "answer": "The meaning of life is a philosophical question that varies depending on individual beliefs and perspectives."
}
```

### All choices
In some scenarios, users may need to obtain the original response of llm to perform some operations. It can be obtained by configuring `response=all` to get the original [LLM response](https://platform.openai.com/docs/api-reference/chat/object).

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
sample:
  inputs:
    first_name: John
    last_name: Doh
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
When `stream=true` is configured in the parameters of a prompty whose output format is text, promptflow sdk will return a generator type, which item is the content of each chunk.
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
sample: 
  "question": "What's the steps to get rich?"
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
Users can retrieve elements from the generator results using the following code.
```python
from promptflow.core import Prompty

# load prompty as a flow
prompty_func = Prompty.load("stream_output.prompty")
# execute the flow as function
question = "What's the steps to get rich?"
result = prompty_func(question=question)
# Type of the result is generator
for item in result:
    print(item, end="")
```