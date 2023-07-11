# Basic
A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in custom connection. 

Tools used in this flow：
- Prompt
- Python Tool

Connections used in this flow:
- Custom Connection

## Prerequisites

install promptflow-sdk and other dependencies:
```bash
pip install -r requirements.txt
```

Ensure you have put your azure open ai endpoint key in .env file.
```bash
cat .env
```

## Run flow in local
### create custom connection

```bash
pf connection create -f .env --name custom_connection
```

### run locally with single line input

```bash
pf flow test --flow . --input data.jsonl
```

### bulk run with multiple lines input

- create bulk run
```bash
pf run create --flow . --type bulk --data ./data.jsonl --stream
```

- list and show run meta
```bash
# list created run
pf run list
# show specific run detail
pf run show --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd

# show output
pf run show-details --name d5a35b24-e7e4-44b3-b6e9-0611a05da9bd
```

