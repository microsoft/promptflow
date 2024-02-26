# Describe image flow
A flow that take image input, flip it horizontally and uses OpenAI GPT-4V tool to describe it.

Tools used in this flow：
- `OpenAI GPT-4V` tool
- custom `python` Tool

Connections used in this flow:
- OpenAI Connection

## Prerequisites

Install promptflow sdk and other dependencies, create connection for OpenAI GPT-4V tool to use:
```bash
pip install -r requirements.txt
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> name=aoai_gpt4v_connection api_version=2023-07-01-preview
```

## Run flow

- Prepare OpenAI connection
Go to "Prompt flow" "Connections" tab. Click on "Create" button, and create an "OpenAI" connection. If you do not have an OpenAI account, please refer to [OpenAI](https://platform.openai.com/) for more details.

- Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs question="How many colors can you see?" input_image="https://developer.microsoft.com/_devcom/images/logo-ms-social.png"

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
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("describe_image_variant_0")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```
