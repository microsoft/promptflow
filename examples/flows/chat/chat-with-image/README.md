# Chat With Image

This flow demonstrates how to create a chatbot that can take image and text as input.

Tools used in this flow：
- `OpenAI GPT-4V` tool

## Prerequisites

Install promptflow sdk and other dependencies in this folder:
```bash
pip install -r requirements.txt
```

## What you will learn

In this flow, you will learn
- how to compose a chat flow with image and text as input. The chat input should be a list of text and/or images.

## Getting started

### 1 Create connection for OpenAI GPT-4V tool to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, and create an "OpenAI" connection. If you do not have an OpenAI account, please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> name=aoai_gpt4v_connection api_version=2023-07-01-preview
```

Note in [flow.dag.yaml](flow.dag.yaml) we are using connection named `aoai_gpt4v_connection`.
```bash
# show registered connection
pf connection show --name aoai_gpt4v_connection
```

### 2 Start chatting

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow .

# run chat flow with new question
pf flow test --flow . --inputs question='["How many colors can you see?", {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"}]'
```

```sh
# start a interactive chat session in CLI
pf flow test --flow . --interactive

# start a interactive chat session in CLI with verbose info
pf flow test --flow . --interactive --verbose
```


