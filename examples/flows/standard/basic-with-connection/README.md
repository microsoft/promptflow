# Basic
A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables. 

Tools used in this flow：
- `prompt` tool
- custom `python` Tool

Connections used in this flow:
- None

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

Create connection if you haven't done that.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set secrets.api_key=<your_api_key> configs.api_base=<your_api_base>
```

Ensure you have created `basic_custom_connection` connection.
```bash
pf connection show -n basic_custom_connection
```

## Run flow in local

### Run locally with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs text="Hello World!"

# test node with inputs
pf flow test --flow . --node llm --inputs prompt="Write a simple Hello World! program that displays the greeting message when executed."

```

### Run with multiple lines data

- create run
```bash
pf run create --flow . --data ./data.jsonl --stream
```

- list and show run meta
```bash
# list created run
pf run list -r 3

# show specific run detail
pf run show --name "basic_with_connection_default_20230724_160757_016682"

# show output
pf run show-details --name "basic_with_connection_default_20230724_160757_016682"

# visualize run in browser
pf run visualize --name "basic_with_connection_default_20230724_160757_016682"
```

### Run with connection overwrite

Ensure you have created `azure_open_ai_connection` connection before.

```bash
pf connection show -n azure_open_ai_connection
```

Create connection if you haven't done that.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Run flow with newly created connection.

```bash
pf run create --flow . --data ./data.jsonl --connections llm.connection=azure_open_ai_connection --stream
```

### Run in cloud with connection overwrite

Ensure you have created `azure_open_ai_connection` connection in cloud. Reference [this notebook](../../../tutorials/get-started/quickstart-azure.ipynb) on how to create connections in cloud with UI.

Run flow with connection `azure_open_ai_connection`.

```bash
# set default workspace
az account set -s 96aede12-2f73-41cb-b983-6d11a904839b
az configure --defaults group="promptflow" workspace="promptflow-eastus"

pfazure run create --flow . --data ./data.jsonl --connections llm.connection=azure_open_ai_connection --stream --runtime demo-mir
```
