# Multi Intent Conversational Language Understanding

A flow that can be used to determine multiple intents in a user query leveraging an LLM with Conversational Language Understanding. 

This sample flow utilizes Azure AI Language's Conversational Language Understanding to perform various analyses on text or documents. It performs:

- Breakdown of compound multi intent user queries into single user queries using an LLM.
- [Conversational Language Understanding](https://learn.microsoft.com/en-us/azure/ai-services/language-service/conversational-language-understanding/overview) on each of those single user queries.

See the [promptflow-azure-ai-language](https://github.com/microsoft/promptflow/blob/main/docs/integrations/tools/azure_ai_language_tool.md) tool package reference documentation for further information. 

Tools used in this flow:
- `LLM` tool
- `conversational_language_understanding` tool from the `promptflow-azure-ai-language` package

Connections used in this flow:
- `Custom` connection

## Prerequisites
Install promptflow sdk and other dependencies:
```
pip install -r requirements.txt
```

## Setup connection
Prepare your [Azure AI Language Resource](https://azure.microsoft.com/en-us/products/ai-services/ai-language) first, and [create a Language Resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesTextAnalytics) if necessary. Import the accompanying MediaPlayer.json into a CLU app, train the app and deploy. From your Language Resource, obtain its `api_key` and `endpoint`.

Create a connection to your Language Resource. The connection uses the `CustomConnection` schema:
```
# Override keys with --set to avoid yaml file changes
pf connection create -f ../connections/azure_ai_language.yml --set secrets.api_key=<your_api_key> configs.endpoint=<your_endpoint> name=azure_ai_language_connection
```
Ensure you have created the `azure_ai_language_connection`:
```
pf connection show -n azure_ai_language_connection
```

## Run flow
```
# Test with default input values in flow.dag.yaml:
pf flow test --flow .
```

### Flow description
The flow uses a `llm` node to break down compound user queries into simple user queries. For example, "Play some blues rock and turn up the volume" will be broken down to "["Play some blues rock", "Turn Up the volume"]".
This is then passed into the CLU tool to recognize intents and entities in each of the utterances.

### Contact
Please reach out to Abhishek Sen (<absen@microsoft.com>) or <taincidents@microsoft.com> with any issues.