# LLM 

## Introduction
Prompt flow LLM tool enables you to leverage widely used large language models like [OpenAI](https://platform.openai.com/), [Azure OpenAI (AOAI)](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/overview), and models in [Azure AI Studio model catalog](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/model-catalog) for natural language processing. 
> [!NOTE]
> The previous version of the LLM tool is now being deprecated. Please upgrade to latest [promptflow-tools](https://pypi.org/project/promptflow-tools/) package to consume new llm tools.

Prompt flow provides a few different LLM APIs:
- **[Completion](https://platform.openai.com/docs/api-reference/completions)**: OpenAI's completion models generate text based on provided prompts.
- **[Chat](https://platform.openai.com/docs/api-reference/chat)**: OpenAI's chat models facilitate interactive conversations with text-based inputs and responses.


## Prerequisite
Create OpenAI resources, Azure OpenAI resources or MaaS deployment with the LLM models (e.g.: llama2, mistral, cohere etc.) in Azure AI Studio model catalog:

- **OpenAI**

    Sign up account [OpenAI website](https://openai.com/)

    Login and [Find personal API key](https://platform.openai.com/account/api-keys)

- **Azure OpenAI (AOAI)**

    Create Azure OpenAI resources with [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal)

- **MaaS deployment**

    Create MaaS deployment for models in Azure AI Studio model catalog with [instruction](https://learn.microsoft.com/en-us/azure/ai-studio/concepts/deployments-overview#deploy-models-with-model-as-a-service-maas)

    You can create serverless connection to use this MaaS deployment.

## **Connections**

Setup connections to provisioned resources in prompt flow.

| Type        | Name     | API KEY  | API BASE |  API Type | API Version |
|-------------|----------|----------|----------|-----------|-------------|
| OpenAI      | Required | Required | -        | -         | -           |
| AzureOpenAI | Required | Required | Required | Required  | Required    |
| Serverless  | Required | Required | Required | -         | -           |


## Inputs
### Text Completion

| Name                   | Type        | Description                                                                             | Required |
|------------------------|-------------|-----------------------------------------------------------------------------------------|----------|
| prompt                 | string      | text prompt that the language model will complete                                       | Yes      |
| model, deployment_name | string      | the language model to use                                                               | Yes      |
| max\_tokens            | integer     | the maximum number of tokens to generate in the completion. Default is 16.              | No       |
| temperature            | float       | the randomness of the generated text. Default is 1.                                     | No       |
| stop                   | list        | the stopping sequence for the generated text. Default is null.                          | No       |
| suffix                 | string      | text appended to the end of the completion                                              | No       |
| top_p                  | float       | the probability of using the top choice from the generated tokens. Default is 1.        | No       |
| logprobs               | integer     | the number of log probabilities to generate. Default is null.                           | No       |
| echo                   | boolean     | value that indicates whether to echo back the prompt in the response. Default is false. | No       |
| presence\_penalty      | float       | value that controls the model's behavior with regards to repeating phrases. Default is 0.                              | No       |
| frequency\_penalty     | float       | value that controls the model's behavior with regards to generating rare phrases. Default is 0.                             | No       |
| best\_of               | integer     | the number of best completions to generate. Default is 1.                               | No       |
| logit\_bias            | dictionary  | the logit bias for the language model. Default is empty dictionary.                     | No       |


### Chat


| Name                   | Type        | Description                                                                                    | Required |
|------------------------|-------------|------------------------------------------------------------------------------------------------|----------|
| prompt                 | string      | text prompt that the language model will response                                              | Yes      |
| model, deployment_name | string      | the language model to use                                                                      | Yes      |
| max\_tokens            | integer     | the maximum number of tokens to generate in the response. Default is inf.                      | No       |
| temperature            | float       | the randomness of the generated text. Default is 1.                                            | No       |
| stop                   | list        | the stopping sequence for the generated text. Default is null.                                 | No       |
| top_p                  | float       | the probability of using the top choice from the generated tokens. Default is 1.               | No       |
| presence\_penalty      | float       | value that controls the model's behavior with regards to repeating phrases. Default is 0.      | No       |
| frequency\_penalty     | float       | value that controls the model's behavior with regards to generating rare phrases. Default is 0.| No       |
| logit\_bias            | dictionary  | the logit bias for the language model. Default is empty dictionary.                            | No       |
| tool\_choice           | object      | value that controls which tool is called by the model. Default is null.                        | No       |
| tools                  | list        | a list of tools the model may generate JSON inputs for. Default is null.                       | No       |
| response_format        | object      | an object specifying the format that the model must output. Default is null.                   | No       |

## Outputs

| Return Type | Description                                                          |
|-------------|----------------------------------------------------------------------|
| string      | The text of one predicted completion or response of conversation     |


## How to use LLM Tool?

1. Setup and select the connections to OpenAI resources
2. Configure LLM model api and its parameters
3. Prepare the Prompt with [guidance](./prompt-tool.md#how-to-write-prompt).

## How to write a chat prompt?

_To grasp the fundamentals of creating a chat prompt, begin with [this section](./prompt-tool.md#how-to-write-prompt) for an introductory understanding of jinja._

We offer a method to distinguish between different roles in a chat prompt, such as "system", "user", "assistant" and "tool". The "system", "user", "assistant" roles can have "name" and "content" properties. The "tool" role, however, should have "tool_call_id" and "content" properties. For an example of a tool chat prompt, please refer to [Sample 3](#sample-3).

### Sample 1
```jinja
# system:
You are a helpful assistant.

{% for item in chat_history %}
# user:
{{item.inputs.question}}
# assistant:
{{item.outputs.answer}}
{% endfor %}

# user:
{{question}}
```

In LLM tool, the prompt is transformed to match the [openai messages](https://platform.openai.com/docs/api-reference/chat/create#chat-create-messages) structure before sending to openai chat API.

```
[
    {
        "role": "system",
        "content": "You are a helpful assistant."
    },
    {
        "role": "user",
        "content": "<question-of-chat-history-round-1>"
    },
    {
        "role": "assistant",
        "content": "<answer-of-chat-history-round-1>"
    },
    ...
    {
        "role": "user",
        "content": "<question>"
    }
]
```

### Sample 2
```jinja
# system:
{# For role naming customization, the following syntax is used #}
## name:
Alice
## content:
You are a bot can tell good jokes.
```

In LLM tool, the prompt is transformed to match the [openai messages](https://platform.openai.com/docs/api-reference/chat/create#chat-create-messages) structure before sending to openai chat API.

```
[
    {
        "role": "system",
        "name": "Alice",
        "content": "You are a bot can tell good jokes."
    }
]
```

### Sample 3
This sample illustrates how to write a tool chat prompt.
```jinja
# system:
You are a helpful assistant.

# user:
What is the current weather like in Boston?

# assistant:
{# The assistant message with 'tool_calls' must be followed by messages with role 'tool'. #}
## tool_calls:
{{llm_output.tool_calls}}

# tool:
{#
Messages with role 'tool' must be a response to a preceding message with 'tool_calls'.
Additionally, 'tool_call_id's should match ids of assistant message 'tool_calls'.
#}
## tool_call_id:
{{llm_output.tool_calls[0].id}}
## content:
{{tool-answer-of-last-question}}

# user:
{{question}}
```

In LLM tool, the prompt is transformed to match the [openai messages](https://platform.openai.com/docs/api-reference/chat/create#chat-create-messages) structure before sending to openai chat API.

```
[
    {
        "role": "system",
        "content": "You are a helpful assistant."
    },
    {
        "role": "user",
        "content": "What is the current weather like in Boston?"
    },
    {
        "role": "assistant",
        "content": null,
        "function_call": null,
        "tool_calls": [
            {
                "id": "<tool-call-id-of-last-question>",
                "type": "function",
                "function": "<function-to-call-of-last-question>"
            }
        ]
    },
    {
        "role": "tool",
        "tool_call_id": "<tool-call-id-of-last-question>",
        "content": "<tool-answer-of-last-question>"
    }
    ...
    {
        "role": "user",
        "content": "<question>"
    }
]
```
