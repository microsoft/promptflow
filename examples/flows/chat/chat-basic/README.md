# Basic Chat
This example shows how to create a basic chat flow. It demonstrates how to create a chatbot that can remember previous interactions and use the conversation history to generate next message.

Tools used in this flow：
- `llm` tool

## Prerequisites

Install promptflow sdk and other dependencies in this folder:
```bash
pip install -r requirements.txt
```

## What you will learn

In this flow, you will learn
- how to compose a chat flow.
- prompt template format of LLM tool chat api. Message delimiter is a separate line containing "#", role name and colon: "# system:", "# user:", "# assistant:".
See <a href="https://platform.openai.com/docs/api-reference/chat/create#chat/create-role" target="_blank">OpenAI Chat</a> for more about message role.
    ```jinja
    # system:
    You are a chatbot having a conversation with a human.

    # user:
    {{question}}
    ```
- how to consume chat history in prompt.
    ```jinja
    {% for item in chat_history %}
    # user:
    {{item.inputs.question}}
    # assistant:
    {{item.outputs.answer}}
    {% endfor %}
    ```

## Getting started

### 1 Create connection for LLM tool to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Note in [flow.dag.yaml](flow.dag.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

### 2 Start chatting

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow .

# run chat flow with new question
pf flow test --flow . --inputs question="What's Azure Machine Learning?"

# start a interactive chat session in CLI
pf flow test --flow . --interactive

# start a interactive chat session in CLI with verbose info
pf flow test --flow . --interactive --verbose
```

