# Basic chat (code-first)
This example shows how to create a basic chat flow using code-first approach. It demonstrates how to create a chatbot that can remember previous interactions and use the conversation history to generate next message.

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
- prompt template format of LLM tool chat api. Message delimiter is a separate line containing role name and colon: "system:", "user:", "assistant:".
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
    user:
    {{item.inputs.question}}
    assistant:
    {{item.outputs.answer}}
    {% endfor %}
    ```


## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](.env) file. You can create one refer to this [example file](.env.example).

```bash
cat .env
```

- Test flow/node

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow .

# run chat flow with new question
pf flow test --flow . --inputs question="What's Azure Machine Learning?"

pf flow test --flow . --inputs question="What is ChatGPT? Please explain with consise statement."
```

- Create run with multiple lines data
```bash
# using environment from .env file (loaded in user code: hello.py)
pf run create --flow . --data ./data.jsonl --column-mapping question='${data.question}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_code_first")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```

## Run flow with connection
Storing connection info in .env with plaintext is not safe. We recommend to use `pf connection` to guard secrets like `api_key` from leak.

- Show or create `open_ai_connection`
```bash
# create connection from `azure_openai.yml` file
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>

# check if connection exists
pf connection show -n open_ai_connection
```

- Test using connection secret specified in environment variables
**Note**: we used `'` to wrap value since it supports raw value without escape in powershell & bash. For windows command prompt, you may remove the `'` to avoid it become part of the value.

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow . --environment-variables OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}'
```

- Create run using connection secret binding specified in environment variables, see [run.yml](run.yml)
```bash
# create run
pf run create --flow . --data ./data.jsonl --stream --environment-variables OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --column-mapping question='${data.question}'
# create run using yaml file
pf run create --file run.yml --stream

# show outputs
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_variant_0")) | .name'| head -n 1 | tr -d '"')
pf run show-details --name $name
```

## Run flow in cloud with connection
- Assume we already have a connection named `open_ai_connection` in workspace.
```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>
```

- Create run
```bash
# run with environment variable reference connection in azureml workspace
pfazure run create --flow . --data ./data.jsonl --environment-variables OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --column-mapping question='${data.question}' --stream
# run using yaml file
pfazure run create --file run.yml --stream
