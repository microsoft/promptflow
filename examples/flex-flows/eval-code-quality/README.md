# Eval Code Quality
A example flow defined using class based entry which leverages model config to evaluate the quality of code snippet.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup connection

Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Or use CLI to create connection:

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Note in [flow.flex.yaml](flow.flex.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

- Run as normal Python file
```bash
python code_quality.py
```

- Test flow
```bash
# correct
pf flow test --flow . --inputs code='print(\"Hello, world!\")' --init init.json

# incorrect
pf flow test --flow . --inputs code='printf("Hello, world!")' --init init.json
```