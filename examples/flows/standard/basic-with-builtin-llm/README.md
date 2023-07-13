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
pf connection create -f azure_openai.yml
```

## Run flow in local

### Run locally with single line input

```bash
pf flow test --flow . --input data.jsonl
```

### Batch run with multiple lines data

- create batch run
```bash
pf run create --flow . --type batch --data ./data.jsonl --stream
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
pf run visualize "18fb849b-7da4-4be8-b989-be22c4b03a13"
```

