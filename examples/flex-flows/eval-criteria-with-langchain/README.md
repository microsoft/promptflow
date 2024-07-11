# Eval Conciseness Criteria with LangChain

A example flow of converting LangChain criteria evaluator application to flex flow.
Reference [here](https://python.langchain.com/docs/guides/productionization/evaluation/string/criteria_eval_chain/) for more information.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.
- Or prepare your Anthropic resource follow this [instruction](https://python.langchain.com/docs/integrations/platforms/anthropic/) and get your `api_key` if you don't have one.

- Setup connection

Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Or use CLI to create connection:

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ./connection.yml --set secrets.openai_api_key=<your_api_key> configs.azure_endpoint=<your_api_base> --name my_llm_connection
```

Note in [flow.flex.yaml](flow.flex.yaml) we are using connection named `my_llm_connection`.
```bash
# show registered connection
pf connection show --name my_llm_connection
```

- Run as normal Python file
```bash
python eval_conciseness.py
```

- Test flow
```bash
pf flow test --flow eval_conciseness:LangChainEvaluator --inputs input="What's 2+2?" prediction="What's 2+2? That's an elementary question. The answer you're looking for is that two and two is four." --init custom_connection=my_llm_connection
```

- Test flow with yaml
```bash
pf flow test --flow .
```

- Create run with multiple lines data

```bash
pf run create --flow . --data ./data.jsonl --init custom_connection=my_llm_connection --stream
```

Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

- List and show run meta

```bash
# list created run
pf run list

# get a sample run name

name=$(pf run list -r 10 | jq '.[] | select(.name | contains("eval_criteria_with_langchain_")) | .name'| head -n 1 | tr -d '"')
# show specific run detail
pf run show --name $name

# show output
pf run show-details --name $name

# show metrics
pf run show-metrics --name $name

# visualize run in browser
pf run visualize --name $name
```

## Run flow in cloud

- Assume we already have a connection named `open_ai_connection` in workspace.

```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>
```

- Create run

```bash
# run with environment variable reference connection in azureml workspace
pfazure run create --flow . --init init.json --data ./data.jsonl --stream
