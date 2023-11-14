# Analyze Documents

A flow that analyzes documents with various language-based Machine Learning models. 

This sample flow utilizes Azure AI Language's pre-built and optimized language models to perform various analyses on text or documents. It performs:
- [Personally Identifiable Information (PII) detection](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/overview)
- [Named Entity Recognition (NER)](https://learn.microsoft.com/en-us/azure/ai-services/language-service/named-entity-recognition/overview)
- [Document Summarization](https://learn.microsoft.com/en-us/azure/ai-services/language-service/summarization/overview?tabs=document-summarization)
- [Sentiment Analysis & Opinion Mining](https://learn.microsoft.com/en-us/azure/ai-services/language-service/sentiment-opinion-mining/overview?tabs=prebuilt)

See the [promptflow-azure-ai-language](https://github.com/microsoft/promptflow/blob/main/docs/integrations/tools/azure_ai_language_tool.md) tool package reference documentation for further information. 

Tools used in this flow:
- `python` tool
- `pii_entity_recognition` tool from the `promptflow-azure-ai-language` package
- `abstractive_summarization` tool from the `promptflow-azure-ai-language` package
- `extractive_summarization` tool from the `promptflow-azure-ai-language` package
- `entity_recognition` tool from the `promptflow-azure-ai-language` package
- `sentiment_analysis` tool from the `promptflow-azure-ai-language` package

Connections used in this flow:
- `Custom` connection

## Prerequisites
Install promptflow sdk and other dependencies:
```
pip install -r requirements.txt
```

## Setup connection
Prepare your [Azure AI Language Resource](https://azure.microsoft.com/en-us/products/ai-services/ai-language) first, and [create a Language Resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesTextAnalytics) if necessary. From your Language Resource, obtain its `api_key` and `endpoint`.

Create a connection to your Language Resource. The connection uses the `CustomConnection` schema:
```
# Override keys with --set to avoid yaml file changes
pf connection create -f ../../../connections/azure_ai_language.yml --set secrets.api_key=<your_api_key> configs.endpoint=<your_endpoint> name=azure_ai_language_connection
```
Ensure you have created the `azure_ai_language_connection`:
```
pf connection show -n azure_ai_language_connection
```

## Run flow

### Run with single line input
```
# Test with default input values in flow.dag.yaml:
pf flow test --flow .
# Test with specific input:
pf flow test --flow . --inputs document_path=<path_to_txt_file> language=<document_language_code>
```

### Run with multiple lines of data
```
pf run create --flow . --data ./data.jsonl --column-mapping document_path='${data.document_path}' language='${data.language}' --stream
```
You can also skip providing column-mapping if provided data has same column name as the flow. Reference [here](https://microsoft.github.io/promptflow/how-to-guides/run-and-evaluate-a-flow/use-column-mapping.html) for default behavior when column-mapping not provided in CLI.

### Flow description
The flow first uses a `python` node to read in the provided `.txt` file into a string. This string is passed to a `pii_entity_recognition` node where Personally Identifiable Information (PII) is redacted. The redacted text is passed to `abstractive_summarization`, `extractive_summarization` and `entity_recognition` nodes, where summaries and named-entities are obtained. Finally, the generated abstractive summary is forwarded to a `sentiment_analysis` node to analyze its general sentiment.

### Contact
Please reach out to Sean Murray (<murraysean@microsoft.com>) with any issues.