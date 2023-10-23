# Basic flow with script tool using custom strong type connection
A basic standard flow with script tool that using custom strong type connection.

Tools used in this flow：
- custom `python` Tool

Connections used in this flow:
- custom strong type connection

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Create connection if you haven't done that.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set secrets.api_key='<your_api_key>' configs.api_base='<your_api_base>'
```

Ensure you have created `normal_custom_connection` connection.
```bash
pf connection show -n normal_custom_connection
```

## Run flow

### Run with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs text="Promptflow"
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

# get a sample run name
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("custom_strong_type")) | .name'| head -n 1 | tr -d '"')

# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# visualize run in browser
pf run visualize --name $name
```

### Run with connection override

Run flow with newly created connection.

```bash
pf run create --flow . --data ./data.jsonl --connections my_script_tool.connection=normal_custom_connection --stream
```

### Run in cloud with connection override

Ensure you have created `normal_custom_connection` connection in cloud. Reference [this notebook](../../../tutorials/get-started/quickstart-azure.ipynb) on how to create connections in cloud with UI.

Run flow with connection `normal_custom_connection`.

```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>

pfazure run create --flow . --data ./data.jsonl --connections my_script_tool.connection=normal_custom_connection --stream --runtime demo-mir
```
