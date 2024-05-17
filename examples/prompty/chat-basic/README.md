# Basic chat
A prompt that uses the chat API to answer questions with chat history, leveraging promptflow connection.


## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## What you will learn

In this flow, you will learn
- how to compose a chat flow.
- prompt template format of chat api. Message delimiter is a separate line containing role name and colon: "system:", "user:", "assistant:".
See <a href="https://platform.openai.com/docs/api-reference/chat/create#chat/create-role" target="_blank">OpenAI Chat</a> for more about message role.
    ```jinja
    system:
    You are a chatbot having a conversation with a human.

    user:
    {{question}}
    ```
- how to consume chat history in prompt.
    ```jinja
    {% for item in chat_history %}
    {{item.role}}:
    {{item.content}}
    {% endfor %}
    ```

## Getting started

### Create connection for prompty to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.


```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Note in [chat.prompty](chat.prompty) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

## Run prompty

- Test flow: single turn
```bash
# run chat flow with default question in flow.flex.yaml
pf flow test --flow chat.prompty

# run chat flow with new question
pf flow test --flow chat.prompty --inputs question="What's Azure Machine Learning?"

# run chat flow with sample.json
pf flow test --flow chat.prompty --inputs sample.json
```

- Test flow: multi turn
```shell
# start test in chat ui
pf flow test --flow chat.prompty --ui
```

- Create run with multiple lines data
```bash
# using environment from .env file (loaded in user code: hello.py)
pf run create --flow chat.prompty --data ./data.jsonl --column-mapping question='${data.question}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("chat_basic_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name
```