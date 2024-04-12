# Basic Eval
A prompt that determines whether a answer is correct.

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## Run prompty

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Test flow
```bash
# sample.json contains messages field which contains the chat conversation.
pf flow test --flow apology.prompty --inputs sample.json
```