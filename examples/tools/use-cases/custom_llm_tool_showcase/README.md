# Flow with custom_llm tool
This is a flow demonstrating how to use a `custom_llm` tool, which enables users to seamlessly connect to a large language model with prompt tuning experience using a `PromptTemplate`.

Tools used in this flow:
- `custom_llm` Tool

Connections used in this flow:
- custom connection

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Create connection if you haven't done that.
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f custom_connection.yml --set secrets.api_key=<your_api_key> configs.api_base=<your_api_base>
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
