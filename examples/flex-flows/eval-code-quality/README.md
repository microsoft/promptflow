# Eval Code Quality
A example flow defined using class based entry which leverages model config to evaluate the quality of code snippet.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup connection

Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Or use CLI to create connection:

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Note in [flow.flex.yaml](flow.flex.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

- Run as normal Python file
```bash
python code_quality.py
```

- Test flow
```bash
# correct
pf flow test --flow . --inputs code='print(\"Hello, world!\")' --init init.json

# incorrect
pf flow test --flow . --inputs code='printf("Hello, world!")' --init init.json
```

- Create run with multiple lines data

```bash
pf run create --flow . --init init.json --data ./data.jsonl --stream
```

Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta

```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("eval_code_quality_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# show metrics
pf run show-metrics --name $name

# visualize run in browser
pf run visualize --name $name
```

## Run flow in cloud

- Assume we already have a connection named `open_ai_connection` in workspace.

```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>
```

- Create run

```bash
# run with environment variable reference connection in azureml workspace
pfazure run create --flow . --init init.json --data ./data.jsonl --stream
