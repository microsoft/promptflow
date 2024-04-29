# Analyze Conversations

A flow that analyzes conversations with various language-based Machine Learning models.

This sample flow utilizes Azure AI Language's pre-built and optimized language models to perform various analyses on conversations. It performs:
- [Language Detection](https://learn.microsoft.com/en-us/azure/ai-services/language-service/language-detection/overview)
- [Key Phrase Extraction](https://learn.microsoft.com/en-us/azure/ai-services/language-service/key-phrase-extraction/overview)
- [Conversational PII](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/how-to-call-for-conversations?tabs=client-libraries)
- [Conversation Summarization](https://learn.microsoft.com/en-us/azure/ai-services/language-service/summarization/overview?tabs=conversation-summarization)

See the [`promptflow-azure-ai-language`](https://pypi.org/project/promptflow-azure-ai-language/) tool package reference documentation for further information.

Tools used in this flow:
- `python` tool.
- `language_detection` tool from the `promptflow-azure-ai-language` package.
- `key_phrase_extraction` tool from the `promptflow-azure-ai-language` package.
- `conversational_pii` tool from the `promptflow-azure-ai-language` package.
- `conversation_summarization` tool from the `promptflow-azure-ai-language` package.

Connections used in this flow:
- `Custom` connection (Azure AI Language).

## Prerequisites

### Prompt flow SDK:
Install promptflow sdk and other dependencies:
```
pip install -r requirements.txt
```

Note: when using the Prompt flow SDK, it may be useful to also install the [`Prompt flow for VS Code`](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) extension (if using VS Code).

### Azure AI/ML Studio:
Start an compute session. Required packages will automatically be installed from the `requirements.txt` file.

## Setup connections
To use the `promptflow-azure-ai-language` package, you must have an [Azure AI Language Resource](https://azure.microsoft.com/en-us/products/ai-services/ai-language). [Create a Language Resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesTextAnalytics) if necessary. From your Language Resource, obtain its `api_key` and `endpoint`.

Create a connection to your Language Resource. The connection uses the `CustomConnection` schema:

### Prompt flow SDK:
```
# Override keys with --set to avoid yaml file changes
pf connection create -f ./connections/azure_ai_language.yml --set secrets.api_key=<your_api_key> configs.endpoint=<your_endpoint> name=azure_ai_language
```
Ensure you have created the `azure_ai_language` connection:
```
pf connection show -n azure_ai_language
```

Note: if you already have an Azure AI Language connection, you do not need to create an additional connection and may substitute it in.

### Azure AI/ML Studio:
If using Azure AI Studio, you will need to add two additional custom keys to the connection. Follow these [instructions](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/prompt-flow-tools/python-tool#create-a-custom-connection)  when creating a `CustomConnection`.

![Azure AI Language Connection](./connections/azure_ai_language.png "Azure AI Language Connection")

## Run flow

### Prompt flow SDK:
```
# Test with default input values in flow.dag.yaml:
pf flow test --flow .
# Test with specific input:
pf flow test --flow . --inputs transcript_path=<path_to_txt_file>
```

### Azure AI/ML Studio:
Run flow.

## Flow Description
The flow first reads in a text file corresponding to a conversation transcript and detects its language. Key phrases are extracted from the transcript, and PII information is redacted. From the redacted transcript information, the flow generates various summaries. These summaries include a general narrative summary, a recap summary, a summary of follow-up tasks, and chapter titles.

This flow showcases a variety of analyses to perform on conversations. Consider extending this flow to generate and extract valuable information from your own meetings/transcripts, such as creating meeting notes, identifying follow-up tasks, etc.

## Contact
Please reach out to Azure AI Language (<taincidents@microsoft.com>) with any issues.