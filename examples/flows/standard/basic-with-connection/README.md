# Basic
A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables. 

Tools used in this flow：
- `prompt` tool
- custom `python` Tool

Connections used in this flow:
- None

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup environment variables

Ensure you have created `basic_custom_connection` connection before.
```bash
pf connection show -n basic_custom_connection
```

Create connection if you haven't done that.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom.yml --set secrets.api_key=<your_api_key> configs.api_base=<your_api_base>
```

## Run flow in local

### Run locally with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### Run with multiple lines data

- create run
```bash
pf run create --flow . --data ./data.jsonl --stream
```

- list and show run meta
```bash
# list created run
pf run list

# show specific run detail
pf run show --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd

# show output
pf run show-details --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd

# visualize run in browser
pf run visualize "d5a35b24-e7e4-44b3-b6e9-0611a05da9bd"
```

