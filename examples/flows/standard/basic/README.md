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
Ensure you have put your azure open ai endpoint key in .env file.
```bash
cat .env
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
pf run show --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd

# show output
pf run show-details --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd

# visualize run in browser
pf run visualize "d5a35b24-e7e4-44b3-b6e9-0611a05da9bd"
```

