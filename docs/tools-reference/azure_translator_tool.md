# Azure Translator

Azure Cognitive Services Translator is a cloud-based machine translation service you can use to translate text in with a simple REST API call. See the [Azure Translator API](https://learn.microsoft.com/en-us/azure/cognitive-services/translator/) for more information.

## Requirements
- requests

## Prerequisites
- Create a Translator resource (https://learn.microsoft.com/en-us/azure/cognitive-services/translator/create-translator-resource).

## Inputs

The following are available input parameters:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| input_text | string | The text to translate. | Yes |
| source_language | string | The language (code) of the input text. | Yes |
| target_language | string | The language (code) you want the text to be translated too. | Yes |

For more information, please refer to [Translator 3.0: Translate](https://learn.microsoft.com/en-us/azure/cognitive-services/translator/reference/v3-0-translate#required-parameters)


## Outputs

The following is an example output returned by the tool:

input_text = "Is this a leap year?"
source_language = "en"
target_language = "hi"


<details>
  <summary>Output</summary>

```
क्या यह एक छलांग वर्ष है?
```
</details>