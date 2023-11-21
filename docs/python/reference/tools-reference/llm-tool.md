# LLM 

## Introduction
Prompt flow LLM tool enables you to leverage widely used large language models like [OpenAI](https://platform.openai.com/) or [Azure OpenAI (AOAI)](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/overview) for natural language processing. 

Prompt flow provides a few different LLM APIs:
- **[Completion](https://platform.openai.com/docs/api-reference/completions)**: OpenAI's completion models generate text based on provided prompts.
- **[Chat](https://platform.openai.com/docs/api-reference/chat)**: OpenAI's chat models facilitate interactive conversations with text-based inputs and responses.
> [!NOTE]
> We now remove the `embedding` option from LLM tool api setting. You can use embedding api with [Embedding tool](https://github.com/microsoft/promptflow/blob/main/docs/reference/tools-reference/embedding_tool.md).


## Prerequisite
Create OpenAI resources:

- **OpenAI**

    Sign up account [OpenAI website](https://openai.com/)
    Login and [Find personal API key](https://platform.openai.com/account/api-keys)

- **Azure OpenAI (AOAI)**

    Create Azure OpenAI resources with [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal)

## **Connections**

Setup connections to provisioned resources in prompt flow.

| Type        | Name     | API KEY  | API Type | API Version |
|-------------|----------|----------|----------|-------------|
| OpenAI      | Required | Required | -        | -           |
| AzureOpenAI | Required | Required | Required | Required    |


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
| frequency\_penalty     | float       | value that controls the model's behavior with regards to generating rare phrases. Default is 0. | No       |
| logit\_bias            | dictionary  | the logit bias for the language model. Default is empty dictionary.                            | No       |



## Outputs

| API        | Return Type | Description                              |
|------------|-------------|------------------------------------------|
| Completion | string      | The text of one predicted completion     |
| Chat       | string      | The text of one response of conversation |


## How to use LLM Tool?

1. Setup and select the connections to OpenAI resources
2. Configure LLM model api and its parameters
3. Prepare the Prompt with [guidance](./prompt-tool.md#how-to-write-prompt).
