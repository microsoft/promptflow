# Prompty output format
A few examples that demos different prompty response format like text, json_object, and how to enable stream output.

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## What you will learn

In this flow, you will learn
- Understand how to handle output format of prompty like: text, json_object.
- Understand how to consume stream output of prompty

## Getting started

### Create connection for prompty to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.


```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Note we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

## Run prompty

- [text format output](./text_format.prompty)
```bash
pf flow test --flow text_format.prompty
```

- [json format output](./json_format.prompty)
```bash
pf flow test --flow json_format.prompty
```

- [all response](./all_response.prompty)
```bash
# TODO
# pf flow test --flow all_response.prompty
```

- [stream output](./stream_output.prompty)
```bash
pf flow test --flow stream_output.prompty
```

- Test flow: multi turn
```powershell
# start test in chat ui
pf flow test --flow stream_output.prompty --ui
```

- Create run with multiple lines data
```bash
pf run create --flow json_format.prompty --data ./data.jsonl --column-mapping question='${data.question}' --stream

pf run create --flow text_format.prompty --data ./data.jsonl --column-mapping question='${data.question}' --stream

pf run create --flow stream_output.prompty --data ./data.jsonl --column-mapping question='${data.question}' --stream

# TODO
# pf run create --flow all_response.prompty --data ./data.jsonl --column-mapping question='${data.question}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta
```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("format_output_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name
```