# Basic Eval
Basic evaluator prompt for QA scenario

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## Run prompty

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.
- Note: you need the new [gpt-35-turbo (0125) version](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#gpt-35-models) to use the json_object response_format feature.
- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Test flow
```bash
pf flow test --flow eval.prompty --env --inputs sample.json
```