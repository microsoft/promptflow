# Apology
A prompt that determines whether a chat conversation contains an apology from the assistant.

## Prerequisites

Install `promptflow-devkit`:
```bash
pip install promptflow-devkit
```

### Create connection for prompty to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Note in [apology.prompty](apology.prompty) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

## Run prompty

- Test flow
```bash
# sample.json contains messages field which contains the chat conversation.
pf flow test --flow apology.prompty --inputs sample.json
pf flow test --flow apology.prompty --inputs sample_no_apology.json
```
