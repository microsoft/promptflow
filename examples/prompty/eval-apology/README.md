# Apology
A prompt that determines whether a chat conversation contains an apology from the assistant.

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

```bash
cat ../.env
```

- Test flow
```bash
# sample.json contains messages field which contains the chat conversation.
pf flow test --flow eval.prompty --inputs sample.json
```