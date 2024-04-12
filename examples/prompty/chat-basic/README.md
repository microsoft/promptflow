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

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Test flow: single turn
```bash
# run chat flow with default question in flow.flex.yaml TODO
# pf flow test --flow chat.prompty

# run chat flow with new question
pf flow test --flow chat.prompty --inputs question="What's Azure Machine Learning?"

# run chat flow with sample.json
pf flow test --flow chat.prompty --inputs sample.json
```

- Test flow: multi turn
```powershell
# start test in interactive terminal (TODO)
pf flow test --flow chat.prompty --interactive

# start test in chat ui (TODO)
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

# visualize run in browser
pf run visualize --name $name
```

## Run prompty with connection
Storing connection info in .env with plaintext is not safe. We recommend to use `pf connection` to guard secrets like `api_key` from leak.

- Test using connection secret specified in environment variables
**Note**: we used `'` to wrap value since it supports raw value without escape in powershell & bash. For windows command prompt, you may remove the `'` to avoid it become part of the value.

```bash
# test with default input value in flow.flex.yaml
pf flow test --flow . --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}'
```

- Create run using connection secret binding specified in environment variables, see [run.yml](run.yml)
```bash
# create run
pf run create --flow . --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --column-mapping question='${data.question}'
# create run using yaml file
pf run create --file run.yml --stream

# show outputs
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("chat_basic_")) | .name'| head -n 1 | tr -d '"')
pf run show-details --name $name
```
