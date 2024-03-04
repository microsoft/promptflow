# Content Safety (Text)

Azure Content Safety is a content moderation service developed by Microsoft that help users detect harmful content from different modalities and languages. This tool is a wrapper for the Azure Content Safety Text API, which allows you to detect text content and get moderation results. See the [Azure Content Safety](https://aka.ms/acs-doc) for more information.

## Requirements

- For AzureML users, the tool is installed in default image, you can use the tool without extra installation.
- For local users,
  `pip install promptflow-tools`
> [!NOTE]
> Content Safety (Text) tool is now incorporated into the latest `promptflow-tools` package. If you have previously installed the package `promptflow-contentsafety`, please uninstall it to avoid the duplication in your local tool list.
  
## Prerequisites

- Create an [Azure Content Safety](https://aka.ms/acs-create) resource.
- Add "Azure Content Safety" connection in prompt flow. Fill "API key" field with "Primary key" from "Keys and Endpoint" section of created resource.

## Inputs

You can use the following parameters as inputs for this tool:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| text | string | The text that need to be moderated. | Yes |
| hate_category | string | The moderation sensitivity for Hate category. You can choose from four options: *disable*, *low_sensitivity*, *medium_sensitivity*, or *high_sensitivity*. The *disable* option means no moderation for hate category. The other three options mean different degrees of strictness in filtering out hate content. The default option is *medium_sensitivity*. | Yes |
| sexual_category | string | The moderation sensitivity for Sexual category. You can choose from four options: *disable*, *low_sensitivity*, *medium_sensitivity*, or *high_sensitivity*. The *disable* option means no moderation for sexual category. The other three options mean different degrees of strictness in filtering out sexual content. The default option is *medium_sensitivity*. | Yes |
| self_harm_category | string | The moderation sensitivity for Self-harm category. You can choose from four options: *disable*, *low_sensitivity*, *medium_sensitivity*, or *high_sensitivity*. The *disable* option means no moderation for self-harm category. The other three options mean different degrees of strictness in filtering out self_harm content. The default option is *medium_sensitivity*. | Yes |
| violence_category | string | The moderation sensitivity for Violence category. You can choose from four options: *disable*, *low_sensitivity*, *medium_sensitivity*, or *high_sensitivity*. The *disable* option means no moderation for violence category. The other three options mean different degrees of strictness in filtering out violence content. The default option is *medium_sensitivity*. | Yes |

For more information, please refer to [Azure Content Safety](https://aka.ms/acs-doc)

## Outputs

The following is an example JSON format response returned by the tool:

<details>
  <summary>Output</summary>
  
```json
{
    "action_by_category": {
      "Hate": "Accept",
      "SelfHarm": "Accept",
      "Sexual": "Accept",
      "Violence": "Accept"
    },
    "suggested_action": "Accept"
  }
```

</details>

The `action_by_category` field gives you a binary value for each category: *Accept* or *Reject*. This value shows if the text meets the sensitivity level that you set in the request parameters for that category.

The `suggested_action` field gives you an overall recommendation based on the four categories. If any category has a *Reject* value, the `suggested_action` will be *Reject* as well.
