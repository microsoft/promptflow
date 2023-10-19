# Basic standard flow
A basic standard flow using custom python tool that calls Azure OpenAI with connection info stored in environment variables. 

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

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](.env) file. You can create one refer to this [example file](.env.example).

```bash
cat .env
```

- Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs text="Java Hello World!"

# test node with inputs
pf flow test --flow . --node llm --inputs prompt="Write a simple Hello World program that displays the greeting message when executed."
```

- Create run with multiple lines data
```bash
# using environment from .env file (loaded in user code: hello.py)
pf run create --flow . --data ./data.jsonl --stream
```

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_variant_0")) | .name'| head -n 1 | tr -d '"')

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
pf flow test --flow . --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${open_ai_connection.api_base}'
```

- Create run using connection secret binding specified in environment variables, see [run.yml](run.yml)
```bash
# create run
pf run create --flow . --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${open_ai_connection.api_base}'
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
pfazure run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_API_BASE='${open_ai_connection.api_base}' --stream --runtime demo-mir
# run using yaml file
pfazure run create --file run.yml --stream --runtime demo-mir
```

- List and show run meta
```bash
# list created run
pfazure run list -r 3

# get a sample run name
name=$(pfazure run list -r 100 | jq '.[] | select(.name | contains("basic_variant_0")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pfazure run show --name $name

# show output
pfazure run show-details --name $name

# visualize run in browser
pfazure run visualize --name $name
```