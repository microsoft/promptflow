# Azure Form Recognizer

Azure Form Recognizer is a cloud-based Azure Applied AI Service that uses machine learning to extract key-value pairs, text, tables and key data from your documents. See the [Azure Form Recognizer API](https://learn.microsoft.com/en-us/azure/applied-ai-services/form-recognizer) for more information.

## Requirements
- requests

## Prerequisites
- Create a Form Recognizer resource (https://learn.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/create-a-form-recognizer-resource).

## Inputs

The following are available input parameters:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| document_url | string | The URL of the document to analyze. The input must be a valid, properly encoded (i.e. encode special characters, such as empty spaces), and publicly accessible URL of one of the supported formats: JPEG, PNG, PDF, TIFF, BMP, or HEIF. | Yes |
| model_id | string | A unique model identifier can be passed in as a string. Prebuilt model IDs supported can be found here: https://aka.ms/azsdk/formrecognizer/models. | Yes |

For more information, please refer to [Form Recognizer: Analyze document](https://learn.microsoft.com/en-us/azure/applied-ai-services/form-recognizer/quickstarts/get-started-sdks-rest-api?pivots=programming-language-rest-api#analyze-document-post-request)


## Outputs

The following is an example output returned by the tool:

document_url = "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/sample-layout.pdf"
model_id = "prebuilt-layout"

<details>
  <summary>Output</summary>

```
{
  "apiVersion":"2023-07-31"
  "content":"UNITED STATES SECURITIES AND EXCHANGE COMMISSION..."
  "modelId":"prebuilt-layout"
  "pages":[...]
  "paragraphs":[...]
  "stringIndexType":"textElements"
  "styles":[...]
  "tables":[...]
}
```
</details>