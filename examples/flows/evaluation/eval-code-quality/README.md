# Eval Code Quality
A example flow shows how to evaluate the quality of code snippet.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](.env) file. You can create one refer to this [example file](.env.example).

```bash
cat .env
```

- Test flow/node
```bash
# correct
pf flow test --flow . --inputs code='print(\"Hello, world!\")'

# incorrect
pf flow test --flow . --inputs code='print("Hello, world!")'
```