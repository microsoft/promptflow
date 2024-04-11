# OpenAI GPT-4V

## Introduction
OpenAI GPT-4V tool enables you to leverage OpenAI's GPT-4 with vision, also referred to as GPT-4V or gpt-4-vision-preview in the API, to take images as input and answer questions about them.

## Prerequisites

- Create OpenAI resources

    Sign up account [OpenAI website](https://openai.com/)
    Login and [Find personal API key](https://platform.openai.com/account/api-keys)

- Get Access to GPT-4 API

    To use GPT-4 with vision, you need access to GPT-4 API. Learn more about [How to get access to GPT-4 API](https://help.openai.com/en/articles/7102672-how-can-i-access-gpt-4)

## Connection

Setup connections to provisioned resources in prompt flow.

| Type        | Name     | API KEY  |
|-------------|----------|----------|
| OpenAI      | Required | Required |

## Inputs

| Name                   | Type        | Description                                                                                    | Required |
|------------------------|-------------|------------------------------------------------------------------------------------------------|----------|
| connection             | OpenAI      | the OpenAI connection to be used in the tool                                                   | Yes      |
| model                  | string      | the language model to use, currently only support gpt-4-vision-preview                         | Yes      |
| prompt                 | string      | The text prompt that the language model will use to generate it's response.                    | Yes      |
| max\_tokens            | integer     | the maximum number of tokens to generate in the response. Default is 512.                      | No       |
| temperature            | float       | the randomness of the generated text. Default is 1.                                            | No       |
| stop                   | list        | the stopping sequence for the generated text. Default is null.                                 | No       |
| top_p                  | float       | the probability of using the top choice from the generated tokens. Default is 1.               | No       |
| presence\_penalty      | float       | value that controls the model's behavior with regards to repeating phrases. Default is 0.      | No       |
| frequency\_penalty     | float       | value that controls the model's behavior with regards to generating rare phrases. Default is 0. | No       |
| detail                 | string      | control over how the model processes the image and generates its textual understanding, default is "auto". [Read more](https://platform.openai.com/docs/guides/vision/low-or-high-fidelity-image-understanding) | No       |

## Outputs

| Return Type | Description                              |
|-------------|------------------------------------------|
| string      | The text of one response of conversation |
