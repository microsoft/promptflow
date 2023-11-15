# Azure AI Language
Azure AI Language enables users with task-oriented and optimized pre-trained language models to effectively understand documents and conversations. This Prompt flow tool is a wrapper for various Azure AI Language APIs. The current list of supported capabilities is as follows:

| Name                                      | Description                                           |
|-------------------------------------------|-------------------------------------------------------|
| Abstractive Summarization                 | Generate abstractive summaries from documents.        |
| Extractive Summarization                  | Extract summaries from documents.                     |
| Conversation Summarization                | Summarize conversations.                              |
| Entity Recognition                        | Recognize and categorize entities in documents.       |
| Key Phrase Extraction                     | Extract key phrases from documents.                   |
| Language Detection                        | Detect the language of documents.                     |
| PII Entity Recognition                    | Recognize and redact PII entities in documents.       |
| Sentiment Analysis                        | Analyze the sentiment of documents.                   |
| Conversational Language Understanding     | Predict intents and entities from user's utterances.  |
| Translator                                | Translate documents.                                  |  

## Requirements
- For AzureML users: 
    follow this [wiki](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/how-to-custom-tool-package-creation-and-usage?view=azureml-api-2#prepare-runtime), starting from `Prepare runtime`. Note that the PyPi package name is `promptflow-azure-ai-language`.
- For local users: 
    ```
    pip install promptflow-azure-ai-language
    ```
## Prerequisites
The tool calls APIs from Azure AI Language. To use it, you must create a connection to an [Azure AI Language resource](https://learn.microsoft.com/en-us/azure/ai-services/language-service/). Create a Language resource first, if necessary.
- In Prompt flow, add a new `CustomConnection`.
    - Under the `secrets` field, specify the resource's API key: `api_key: <Azure AI Language Resource api key>`
    - Under the `configs` field, specify the resource's endpoint: `endpoint: <Azure AI Language Resource endpoint>`

To use the `Translator` tool, you must set up an additional connection to an [Azure AI Translator resource](https://azure.microsoft.com/en-us/products/ai-services/ai-translator). [Create a Translator resource](https://learn.microsoft.com/en-us/azure/ai-services/translator/create-translator-resource) first, if necessary.
- In Prompt flow, add a new `CustomConnection`.
    - Under the `secrets` field, specify the resource's API key: `api_key: <Azure AI Translator Resource api key>`
    - Under the `configs` field, specify the resource's endpoint: `endpoint: <Azure AI Translator Resource endpoint>`
    - If your Translator Resource is regional and non-global, specify its region under `configs` as well: `region: <Azure AI Translator Resource region>`

## Inputs
The tool accepts the following inputs:

- **Abstractive Summarization**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | query              | string           | The query used to structure summarization. | Yes |
    | summary_length     | string (enum)    | The desired summary length. Enum values are `short`, `medium`, and `long`. | No |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Extractive Summarization**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | query              | string           | The query used to structure summarization. | Yes |
    | sentence_count     | int              | The desired number of output summary sentences. Default value is `3`. | No |
    | sort_by            | string (enum)    | The sorting criteria for extractive summarization results. Enum values are `Offset` to sort results in order of appearance in the text and `Rank` to sort results in order of importance (i.e. rank score) according to model. Default value is `Offset`. | No |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Conversation Summarization**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. Text should be of the following form: `<speaker id>: <speaker text> \n <speaker id>: <speaker text> \n ...` | Yes |
    | modality           | string (enum)    | The modality of the input text. Enum values are `text` for input from a text source, and `transcript` for input from a transcript source. | Yes |
    | summary_aspect     | string (enum)    | The desired summary "aspect" to obtain. Enum values are `chapterTitle` to obtain the chapter title of any conversation, `issue` to obtain the summary of issues in transcripts of web chats and service calls between customer-service agents and customers, `narrative` to obtain the generic summary of any conversation, `resolution` to obtain the summary of resolutions in transcripts of web chats and service calls between customer-service agents and customers, `recap` to obtain a general summary, and `follow-up tasks` to obtain a summary of follow-up or action items. | Yes |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Entity Recognition**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Key Phrase Extraction**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Language Detection**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | text               | string           | The input text. | Yes |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **PII Entity Recognition**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | domain             | string (enum)    | The PII domain used for PII Entity Recognition. Enum values are `none` for no domain, or `phi` to indicate that entities in the Personal Health domain should be redacted. Default value is `none`. | No |
    | categories         | list[string]     | Describes the PII categories to return. Default value is `[]`. | No |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Sentiment Analysis**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | text               | string           | The input text. | Yes |
    | opinion_mining     | bool             | Should opinion mining be enabled. Default value is `False`. | No |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Conversational Language Understanding**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Language resource. | Yes |
    | language           | string           | The ISO 639-1 code for the language of the input. | Yes |
    | utterances         | string           | A single user utterance or a json array of user utterances. | Yes |
    | project_name       | string           | The Conversational Language Understanding project to be called. | Yes |
    | deployment_name    | string           | The Conversational Language Understanding project deployment to be called. | Yes |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

- **Translator**:
    | Name               | Type             | Description | Required |
    |--------------------|------------------|-------------|----------|
    | connection         | CustomConnection | The created connection to an Azure AI Translator resource. | Yes |
    | text               | string           | The input text. | Yes |
    | to                 | list[string]     | The languages to translate the input text to. | Yes |
    | source_language    | string           | The language of the input text. | No |
    | parse_response     | bool             | Should the raw API json output be parsed. Default value is `False`. | No |

## Outputs
If the input parameter `parse_response` is set to `False` (default value), the raw API json output will be returned as a string. Refer to the [REST API reference](https://learn.microsoft.com/en-us/rest/api/language/) for details on API output. For Conversational Language Understanding, the output will be a list of raw API json responses, one response for each user utterance in the input. 

When `parse_response` is set to `True`, the tool will parse API output as follows:


| Name | Type | Description |
|-------------------------------------------------------------|--------|---------------------|
| Abstractive Summarization | string | Abstractive summary. |
| Extractive Summarization | list[string] | Extracted summary sentence strings. |
| Conversation Summarization | string | Conversation summary based on `summary_aspect`. |
| Entity Recognition | dict[string, string] | Recognized entities, where keys are entity names and values are entity categories. |
| Key Phrase Extraction | list[string] | Extracted key phrases as strings. |
| Language Detection | string | Detected language's ISO 639-1 code. |
| PII Entity Recognition | string | Input `text` with PII entities redacted. |
| Sentiment Analysis | string | Analyzed sentiment: `positive`, `neutral`, or `negative`. |
| Conversational Language Understanding | list[dict[string, string]] | List of user utterances and associated intents. |
| Translator | dict[string, string] | Translated text, where keys are the translated languages and values are the translated texts. |
