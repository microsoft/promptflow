# Basic
A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables. 

Tools used in this flow：
- `prompt` tool
- built-in `llm` tool

Connections used in this flow:
- `azure_open_ai` connection

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connections
Ensure you have created `azure_open_ai_connection` connection before.
```bash
pf connection show -n azure_open_ai_connection
```

Create connection if you haven't done that. Ensure you have put your azure open ai endpoint key in [azure_openai.yml](azure_openai.yml) file. 
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## Run flow in local

### Run locally with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### run with multiple lines data

- create run
```bash
pf run create --flow . --data ./data.jsonl --stream
```

- list and show run meta
```bash
# list created run
pf run list

# show specific run detail
pf run show --name "18fb849b-7da4-4be8-b989-be22c4b03a13"

# show output
pf run show-details --name "18fb849b-7da4-4be8-b989-be22c4b03a13"

# visualize run in browser
pf run visualize -n "18fb849b-7da4-4be8-b989-be22c4b03a13"
```

