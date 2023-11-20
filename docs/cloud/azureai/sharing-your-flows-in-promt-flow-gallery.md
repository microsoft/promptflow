# Sharing Your Flows in Prompt Flow Gallery

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../../how-to-guides/faq.md#stable-vs-experimental).
:::

In this document, we will walk you through the steps to share your flows in Prompt Flow Gallery. This needs to register your flow as a model with specific flow metadata in an organization registry. Once completed, the model will be shown as a flow example in Prompt Flow Gallery on the workspace portal page.

## Registering your flow in AzureML Registry

### Creating a `README.md` file for your flow

To make the flow easily understandable, include a `README.md` file in the flow folder explaining how to use it. The README may contain the following sections:
1. The purpose of the flow.
2. The tools utilized in the flow.
3. The prerequisites required to execute the flow.
4. The knowledge that can be acquired from this flow.
5. The execution process of the flow.
6. Any additional information about your flow.

See this [example README](https://github.com/microsoft/promptflow/blob/main/examples/flows/chat/chat-with-wikipedia/README.md) with sections addressing points 1 to 5. A well-written README improves discoverability and enables collaboration.

### Preparing flow metadata for gallery display

To registry the flow as a model in registry, we need to prepare a model yaml file with some flow metadata. Here, we will primarily focus on the properties related to the UI display of this flow. For more details on other model fields, please refer to [model yaml schema](https://learn.microsoft.com/en-us/azure/machine-learning/reference-yaml-model?view=azureml-api-2). Below is a `model.yml` template for the flow:

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/model.schema.json
name: <model_name>
type: custom_model
path: <the relative path from this model file to the flow folder>
description: <model_description>
version: <model_version>
properties:
  is-promptflow: true
  azureml.promptflow.section: gallery
  azureml.promptflow.type: <flow_type>
  azureml.promptflow.name: <flow_name>
  azureml.promptflow.description: <flow_description>
```

Properties related to the UI display of this flow include:
1. `is-promptflow`: value should always be `true`. This property differentiates it from other models, enabling promptflow service to filter it out.
2. `azureml.promptflow.section`: value should always be `gallery`. This property indicates UI that this flow needs to be shown in the Flow Gallery.
3. `azureml.promptflow.type`: value can be `chat`, `standard` or `evaluate`. This property identifies the type of your flow, and UI will display flows with  `evaluate` value under the 'Evaluation' tab, and display flows with other values under the 'Flow' tab.
4. `azureml.promptflow.name`: the name of the flow which will be shown as the flow name in the Flow Gallery.
5. `azureml.promptflow.description`: the description of the flow which will be shown as flow description in the Flow Gallery.

Take [this existing flow](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-with-wikipedia) as an example, the `model.yml` for it will look like below:
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/model.schema.json
name: chat-with-wikipedia-in-org
type: custom_model
path: chat_with_wikipedia
description: promptflow flow registered as a custom model
version: 1
properties:
  is-promptflow: true
  azureml.promptflow.section: gallery
  azureml.promptflow.type: chat
  azureml.promptflow.name: Chat with Wikipedia in Org
  azureml.promptflow.description: ChatGPT-based chatbot that leverages Wikipedia data to ground the responses.
```

### Register the model in an organization registry

 Run the command below to register the flow as a model to an organization registry. More details about [registry creation](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-registries?view=azureml-api-2&tabs=studio#create-a-registry) and [model creation](https://learn.microsoft.com/en-us/cli/azure/ml/model?view=azure-cli-latest#az-ml-model-create):
```
az ml model create -f model.yml --registry-name <organization-registry-name>
```

## Locate the flow in the Flow Gallery

- Open a workspace in a region supported by the organization registry.
- Click the `Create` button to open the Flow Gallery, and you can find the flow registered before:

![organization examples in flow gallery](../../media/cloud/azureml/org_examples_in_flow_gallery.png)

1. `azureml.promptflow.type`: flows with  `evaluate` value will be displayed under the 'Evaluation' tab, while flows with other values will appear under the 'Flow' tab.
2. `azureml.promptflow.name`: shown as flow name in the flow card.
3. `azureml.promptflow.description`: shown as flow description in the flow card.
4. `readme.md`: click the `View detail` button will show the content in the `readme.md`.