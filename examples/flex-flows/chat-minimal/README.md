# Minimal chat
A chat flow defined using function with minimal code. It demonstrates the minimal code to have a chat flow.

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

## Run flow

- Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure OpenAI endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Run as normal Python file

```bash
python flow.py
```
- Test flow

```bash
pf flow test --flow flow:chat --inputs question="What's the capital of France?"
```

- Test flow: multi turn
```shell
# start test in chat ui
pf flow test --flow flow:chat --ui 
```

- Create run with multiple lines data

```bash
pf run create --flow flow:chat --data ./data.jsonl --column-mapping question='${data.question}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("chat_minimal_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```