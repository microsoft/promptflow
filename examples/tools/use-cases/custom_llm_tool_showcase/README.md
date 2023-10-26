# Flow with custom_llm tool
A flow to demonstrate the usage of the `custom_llm` tool. 

Tools used in this flow:
- `custom_llm` Tool

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

## Run flow

- Test flow
```bash
pf flow test --flow .
```
