[WIP]
# Flow with package tool using custom strong type connection
A basic flow using a package tool that using a custom strong type connection. For how to write your own custom strong type connection, please refer to this [document](../../../../docs/how-to-guides/develop-a-tool/create-your-own-custom-strong-type-connection.md).

Tools used in this flow：
- Package Tool

Connections used in this flow:
- Custom strong type connection

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Create a YAML file with below content:
```yaml
name: "my_second_connection"
type: custom
custom_type: MySecondConnection
module: my_tool_package.connections
package: test-custom-tools
package_version: 0.0.2
configs:
  api_base: "This is a fake api base."
secrets:
  api_key: ""

```

Create the custom strong type connection via pf command.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set secrets.api_key=<your_api_key> configs.api_base=<your_api_base>
```

Ensure you have created `my_second_connection` connection.
```bash
pf connection show -n my_second_connection
```


## Run flow

```bash
# test with default input value in flow.dag.yaml 
pf flow test --flow . 
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
- Assume we already have a connection named `my_second_connection` in workspace.
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