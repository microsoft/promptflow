# LLM Vision

## Introduction
Prompt flow LLM vision tool enables you to leverage your AzureOpenAI GPT-4 Turbo or OpenAI's GPT-4 with vision to analyze images and provide textual responses to questions about them.

## Prerequisites
Create OpenAI or Azure OpenAI resources:

- **OpenAI**

    Sign up account [OpenAI website](https://openai.com/)

    Login and [Find personal API key](https://platform.openai.com/account/api-keys)

- **Azure OpenAI (AOAI)**

    Create Azure OpenAI resources with [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal)

    Browse to [Azure OpenAI Studio](https://oai.azure.com/) and sign in with the credentials associated with your Azure OpenAI resource. During or after the sign-in workflow, select the appropriate directory, Azure subscription, and Azure OpenAI resource.

    Under Management select Deployments and Create a GPT-4 Turbo with Vision deployment by selecting model name: `gpt-4` and model version `vision-preview`.


   
## **Connections**

Setup connections to provisioned resources in prompt flow.

| Type        | Name     | API KEY  | API Type | API Version |
|-------------|----------|----------|----------|-------------|
| OpenAI      | Required | Required | -        | -           |
| AzureOpenAI | Required | Required | Required | Required    |

## Inputs

| Name                    | Type        | Description                                                                                    | Required |
|-------------------------|-------------|------------------------------------------------------------------------------------------------|----------|
| model, deployment\_name | string      | the language model to use                                                                      | Yes      |
| prompt                  | string      | The text prompt that the language model will use to generate it's response.                    | Yes      |
| max\_tokens             | integer     | the maximum number of tokens to generate in the response. Default is 512.                      | No       |
| temperature             | float       | the randomness of the generated text. Default is 1.                                            | No       |
| stop                    | list        | the stopping sequence for the generated text. Default is null.                                 | No       |
| top_p                   | float       | the probability of using the top choice from the generated tokens. Default is 1.               | No       |
| presence\_penalty       | float       | value that controls the model's behavior with regards to repeating phrases. Default is 0.      | No       |
| frequency\_penalty      | float       | value that controls the model's behavior with regards to generating rare phrases. Default is 0.| No       |

## Outputs

| Return Type | Description                              |
|-------------|------------------------------------------|
| string      | The text of one response of conversation |
