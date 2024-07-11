# Basic prompty
A basic prompt that uses the chat API to answer questions, with connection configured using environment variables.

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## Run prompty

- Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.
- Setup environment variables

Ensure you have put your azure OpenAI endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Test prompty
```bash
# test with default sample data 
# --env to use environment variable from .env 
pf flow test --flow basic.prompty --env

# test with flow inputs
pf flow test --flow basic.prompty --env --inputs question="What is the meaning of life?"

# test with another sample data
pf flow test --flow basic.prompty --env --inputs sample.json
```

- Create run with multiple lines data
```bash
# using environment from .env file
pf run create --flow basic.prompty --env --data ./data.jsonl --column-mapping question='${data.question}' --stream
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

## Run prompty with connection

Storing connection info in .env with plaintext is not safe. We recommend to use `pf connection` to guard secrets like `api_key` from leak.

- Show or create `open_ai_connection`
```bash
# create connection from `azure_openai.yml` file
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>

# check if connection exists
pf connection show -n open_ai_connection
```

- Test using connection secret specified in environment variables
**Note**: we used `'` to wrap value since it supports raw value without escape in powershell & bash. For windows command prompt, you may remove the `'` to avoid it become part of the value.

```bash
# test with default input value in flow.flex.yaml
pf flow test --flow basic.prompty --inputs sample.json --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}'
```

- Create run using connection secret binding specified in environment variables, see [run.yml](run.yml)
```bash
# create run
pf run create --flow basic.prompty --data ./data.jsonl --stream --environment-variables AZURE_OPENAI_API_KEY='${open_ai_connection.api_key}' AZURE_OPENAI_ENDPOINT='${open_ai_connection.api_base}' --column-mapping question='${data.question}'
# create run using yaml file
pf run create --file run.yml --stream

# show outputs
name=$(pf run list -r 10 | jq '.[] | select(.name | contains("basic_")) | .name'| head -n 1 | tr -d '"')
pf run show-details --name $name
```
