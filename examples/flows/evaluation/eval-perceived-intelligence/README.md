# Perceived Intelligence Evaluation

This is a flow leverage llm to eval perceived intelligence.
Perceived intelligence is the degree to which a bot can impress the user with its responses, by showing originality, insight, creativity, knowledge, and adaptability.

Tools used in this flow：
- `python` tool
- built-in `llm` tool

### 0. Setup connection

Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

### 1. Test flow/node

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --column-mapping question='${data.question}' answer='${data.answer}' context='${data.context}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.
