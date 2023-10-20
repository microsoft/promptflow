# Basic flow with builtin llm tool
A basic standard flow that calls Azure OpenAI with builtin llm tool. 

Tools used in this flow：
- `prompt` tool
- built-in `llm` tool

Connections used in this flow:
- `azure_open_ai` connection

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

Note in this example, we are using [chat api](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/chatgpt?pivots=programming-language-chat-completions), please use `gpt-35-turbo` or `gpt-4` model deployment.

Ensure you have created `open_ai_connection` connection before.
```bash
pf connection show -n open_ai_connection
```

Create connection if you haven't done that. Ensure you have put your azure open ai endpoint key in [azure_openai.yml](../../../connections/azure_openai.yml) file. 
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f ../../../connections/azure_openai.yml --name open_ai_connection --set api_key=<your_api_key> api_base=<your_api_base>
```


## Run flow

### Run with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with inputs
pf flow test --flow . --inputs text="Python Hello World!"
```

### run with multiple lines data

- create run
```bash
pf run create --flow . --data ./data.jsonl --column-mapping text='${data.text}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- list and show run meta
```bash
# list created run
pf run list

# get a sample run name
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_with_builtin_llm")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```

