# Basic standard flow
A basic standard flow define using function entry that calls Azure OpenAI with connection info stored in environment variables.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure OpenAI endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Run/Debug as normal Python file
```bash
python programmer.py
```

- Test with flow entry
```bash
pf flow test --flow programmer:write_simple_program --inputs text="Java Hello World!"
```

- Test with flow yaml
```bash
# test with sample input value in flow.flex.yaml
pf flow test --flow .
```

```shell
# test with UI
pf flow test --flow . --ui
```

- Create run with multiple lines data
```bash
# using environment from .env file (loaded in user code: hello.py)
pf run create --flow . --data ./data.jsonl --column-mapping text='${data.text}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
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
pfazure run create --flow . --data ./data.jsonl --column-mapping text='${data.text}' --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --stream
# run using yaml file
pfazure run create --file run.yml --stream
```

- List and show run meta
```bash
# list created run
pfazure run list -r 3

# get a sample run name
name=$(pfazure run list -r 100 | jq '.[] | select(.name | contains("basic_")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pfazure run show --name $name

# show output
pfazure run show-details --name $name

# visualize run in browser
pfazure run visualize --name $name
```
