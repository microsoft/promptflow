# Basic standard flow with Unify AI
A basic standard flow define using function entry that calls Unify AI. 

Unify AI helps you use a LLM from a wide variety of models and providers using a single Unify API key. You can make an optimal choice by comparing trade-offs between quality, cost and latency. 

Refer [Unify AI documentation](https://unify.ai/docs).

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Unify AI account follow this [instruction](https://unify.ai/docs/index.html#getting-started) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your Unify key in [.env](./.env) file. You can create one refer to this [example file](./.env.example).

```bash
cat ./.env
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

```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>
```

- Create run
```bash
# run with environment variable reference connection in azureml workspace
pfazure run create --flow . --data ./data.jsonl --column-mapping text='${data.text}' --environment-variables UNIFY_AI_API_KEY='<unify_api_key>' UNIFY_AI_BASE_URL='https://api.unify.ai/v0/' --stream
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
