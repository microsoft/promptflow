# Azure Language Detector

Azure Language Detector is a cloud-based service which you can use to identify the language of a piece of text. See the [Azure Language Detector API](https://learn.microsoft.com/en-us/azure/cognitive-services/translator/reference/v3-0-detect) for more information.

## Requirements
- requests

## Prerequisites
- Create a Translator resource (https://learn.microsoft.com/en-us/azure/cognitive-services/translator/create-translator-resource).

## Inputs

The following are available input parameters:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| input_text | string | Identify the language of the input text. | Yes |

For more information, please refer to [Translator 3.0: Detect](https://learn.microsoft.com/en-us/azure/cognitive-services/translator/reference/v3-0-detect)


## Outputs

The following is an example output returned by the tool:

input_text = "Is this a leap year?"


<details>
  <summary>Output</summary>

```
en
```
</details>