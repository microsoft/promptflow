# Azure AI Language
Azure AI Language enables users with task-oriented and optimized pre-trained or custom language models to effectively understand and analyze documents and conversations. This Prompt flow tool is a wrapper for various Azure AI Language APIs. The current list of supported capabilities is as follows:

| Name                                      | Description                                           |
|-------------------------------------------|-------------------------------------------------------|
| Abstractive Summarization                 | Generate abstractive summaries from documents.        |
| Extractive Summarization                  | Extract summaries from documents.                     |
| Conversation Summarization                | Summarize conversations.                              |
| Entity Recognition                        | Recognize and categorize entities in documents.       |
| Key Phrase Extraction                     | Extract key phrases from documents.                   |
| Language Detection                        | Detect the language of documents.                     |
| PII Entity Recognition                    | Recognize and redact PII entities in documents.       |
| Conversational PII                        | Recognize and redact PII entities in conversations.   |
| Sentiment Analysis                        | Analyze the sentiment of documents.                   |
| Conversational Language Understanding     | Predict intents and entities from user's utterances.  |
| Translator                                | Translate documents.                                  |  

## Requirements
PyPI package: [`promptflow-azure-ai-language`](https://pypi.org/project/promptflow-azure-ai-language/).
- For AzureML users: 
    follow this [wiki](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/how-to-custom-tool-package-creation-and-usage?view=azureml-api-2#prepare-compute-session), starting from `Prepare compute session`.
- For local users: 
    ```
    pip install promptflow-azure-ai-language
    ```
    You may also want to install the [Prompt flow for VS Code extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).
## Prerequisites
The tool calls APIs from Azure AI Language. To use it, you must create a connection to an [Azure AI Language resource](https://learn.microsoft.com/en-us/azure/ai-services/language-service/). [Create a Language Resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesTextAnalytics) first, if necessary.
- In Prompt flow, add a new `CustomConnection`.
    - Under the `secrets` field, specify the resource's API key: `api_key: <Azure AI Language Resource api key>`
    - Under the `configs` field, specify the resource's endpoint: `endpoint: <Azure AI Language Resource endpoint>`

To use the `Translator` tool, you must set up an additional connection to an [Azure AI Translator resource](https://azure.microsoft.com/en-us/products/ai-services/ai-translator). [Create a Translator resource](https://learn.microsoft.com/en-us/azure/ai-services/translator/create-translator-resource) first, if necessary.
- In Prompt flow, add a new `CustomConnection`.
    - Under the `secrets` field, specify the resource's API key: `api_key: <Azure AI Translator Resource api key>`
    - Under the `configs` field, specify the resource's endpoint: `endpoint: <Azure AI Translator Resource endpoint>`
    - If your Translator Resource is regional and non-global, specify its region under `configs` as well: `region: <Azure AI Translator Resource region>`

## Inputs
When a tool parameter is of type `Document`, it requires a `dict` object of [this](https://learn.microsoft.com/en-us/rest/api/language/text-analysis-runtime/analyze-text?view=rest-language-2023-04-01&tabs=HTTP#multilanguageinput) specification.

Example:
```
my_document = {
    "id": "1",
    "text": "This is some document text!",
    "language": "en"
}
```
When a tool parameter is of type `Conversation`, it requires a `dict` object.

Example:
```
my_conversation = {
    "id": "meeting_1",
    "language": "en",
    "modality": "text",
    "domain": "generic",
    "conversationItems": [
        {
            "participantId": "person1",
            "role": "generic",
            "id": "1",
            "text": "Hello!"
        },
        {
            "participantId": "person2",
            "role": "generic",
            "id": "2",
            "text": "How are you?"
        }
    ]
}
```
---------------------------
All skills have the following (optional) inputs:
| Name               | Type             | Description | Required |
|--------------------|------------------|-------------|----------|
| max_retries        | int              | The maximum number of HTTP request retries. Default value is `5`. | No |
| max_wait           | int              | The maximum wait time (in seconds) in-between HTTP requests. Default value is `60`. | No |
| parse_response     | bool             | Should the full API JSON output be parsed to extract the single task result. Default value is `False`. | No |

HTTP request logic utilizes [exponential backoff](https://en.wikipedia.org/wiki/Exponential_backoff). 
See skill specific inputs below:

---------------------------
| Abstractive Summarization | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
|| query              | string           | The query used to structure summarization. | Yes |
|| summary_length     | string (enum)    | The desired summary length. Enum values are `short`, `medium`, and `long`. | No |
---------------------------
| Extractive Summarization | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
|| query              | string           | The query used to structure summarization. | Yes |
|| sentence_count     | int              | The desired number of output summary sentences. Default value is `3`. | No |
|| sort_by            | string (enum)    | The sorting criteria for extractive summarization results. Enum values are `Offset` to sort results in order of appearance in the text and `Rank` to sort results in order of importance (i.e. rank score) according to model. Default value is `Offset`. | No |
---------------------------
| Conversation Summarization | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| conversation       | `Conversation`   | The input conversation. | Yes |
|| summary_aspect     | string (enum)    | The desired summary "aspect" to obtain. Enum values are `chapterTitle` to obtain the chapter title of any conversation, `issue` to obtain the summary of issues in transcripts of web chats and service calls between customer-service agents and customers, `narrative` to obtain the generic summary of any conversation, `resolution` to obtain the summary of resolutions in transcripts of web chats and service calls between customer-service agents and customers, `recap` to obtain a general summary, and `follow-up tasks` to obtain a summary of follow-up or action items. | Yes |
---------------------------
| Entity Recognition | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
---------------------------
| Key Phrase Extraction | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
---------------------------
| Language Detection | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| text               | string           | The input text. | Yes |
---------------------------
| PII Entity Recognition | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
|| domain             | string (enum)    | The PII domain used for PII Entity Recognition. Enum values are `none` for no domain, or `phi` to indicate that entities in the Personal Health domain should be redacted. Default value is `none`. | No |
|| pii_categories     | list[string]     | Describes the PII categories to return. | No |
---------------------------
| Conversational PII | Name               | Type             | Description | Required |
|-|-----------------------|------------------|-------------|----------|
|| connection             | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| conversation           | `Conversation`   | The input conversation. | Yes |
|| pii_categories         | list[string]     | Describes the PII categories to return for detection. Default value is `['Default']`. | No |
|| redact_audio_timing    | bool             | Should audio stream offset and duration for any detected entities be redacted. Default value is `False`. | No |
|| redaction source       | string (enum)    | For transcript conversations, this parameter provides information regarding which content type should be used for entity detection. The details of the entities detected - such as the offset, length, and the text itself - will correspond to the text type selected here. Enum values are `lexical`, `itn`, `maskedItn`, and `text`. Default value is `lexical`. | No |
|| exclude_pii_categories | list[string]     | Describes the PII categories to exclude for detection. Default value is `[]`. | No |

---------------------------
| Sentiment Analysis | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| document           | `Document`       | The input document. | Yes |
|| opinion_mining     | bool             | Should opinion mining be enabled. Default value is `False`. | No |
---------------------------
| Conversational Language Understanding | Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
|| language           | string           | The ISO 639-1 code for the language of the input. | Yes |
|| utterances         | string           | A single user utterance or a json array of user utterances. | Yes |
|| project_name       | string           | The Conversational Language Understanding project to be called. | Yes |
|| deployment_name    | string           | The Conversational Language Understanding project deployment to be called. | Yes |
---------------------------
| Translator |Name               | Type             | Description | Required |
|-|--------------------|------------------|-------------|----------|
|| connection         | CustomConnection | The created connection to an Azure AI Translator resource. | Yes |
|| text               | string           | The input text. | Yes |
|| to                 | list[string]     | The languages to translate the input text to. | Yes |
|| source_language    | string           | The language of the input text. | No |
|| category           | string           | The category (domain) of the translation. This parameter is used to get translations from a customized system built with Custom Translator. Default value is `general`. | No |
|| text_type          | string (enum)    | The type of the text being translated. Possible values are `plain` (default) or `html`. | No |

## Outputs
- When the input parameter `parse_response` is set to `False` (default value), the full API JSON response will be returned (as a `dict` object).
- When the input parameter `parse_response` is set to `True`, the full API JSON response will be parsed to extract the single task result associated with the tool's given skill. Output will depend on the skill (but will still be a `dict` object).
- **Note:** for Conversational Language Understanding (CLU), output will be a list of responses (either full or parsed), one for each detected user utterance in the input.

Refer to Azure AI Language's [REST API reference](https://learn.microsoft.com/en-us/rest/api/language/) for details on API response format, specific task result formats, etc.

## Sample Flows
Find example flows using the `promptflow-azure-ai-language` package [here](https://github.com/microsoft/promptflow/tree/main/examples/flows/integrations/azure-ai-language).

## Contact
Please reach out to Azure AI Language (<taincidents@microsoft.com>) with any issues.