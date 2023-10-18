# Flow Example Sharing in Organization

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Flow developers may want to share their flows within their organization to enhance collaborative development. In this document, we will provide a detailed walkthrough on how to share a flow as a model in an organization registry. Additionally, we will demonstrate how to locate a flow in the Flow gallery.

## How to share flow as a model in an organization registry
In order to share the flow, we need to register the flow as a model with some specific properties in an organization registry.

### Prepare a `readme.md` file for the flow
In order to make the flow easily understand, it is better to add an `readme.md` for the flow in the flow folder. Here we take [this existing readme](https://github.com/microsoft/promptflow/blob/main/examples/flows/chat/chat-with-wikipedia/README.md) as example:
It included below parts in the readme file:
- What the flow is used to.
- What kinds of tools used in the flow.
- Prerequisites needed to run the flow.
- What you will learn from this flow.
Anything else you want others to know about your flow.

> [!Note] This `readme.md` is optional. But we recommend you to add this file for your flow so that it can be easily and quickly understood.


### Prepare a model yaml for the flow
In this section, we will concentrate on the model properties related to this flow's UI display. For information on other model fields, please refer to [model yaml schema](https://learn.microsoft.com/en-us/azure/machine-learning/reference-yaml-model?view=azureml-api-2). Below is the `model.yml` file for flow:

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/model.schema.json
name: <model_name>
type: custom_model
path: <relative path from this model file to flow folder>
description: <model_description>
version: <model_version>
properties:
  is-promptflow: true
  azureml.promptflow.section: gallery
  azureml.promptflow.type: <flow_type>
  azureml.promptflow.name: <flow_name>
  azureml.promptflow.description: <flow_description>
```

Here we use [this existing flow](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-with-wikipedia) as an example to introduce the model properties:
1. `is-promptflow`: value will always be `true`. This property distinguishes it from other models, enabling us to filter and display it in the Flow gallery.
2. `azureml.promptflow.section`: value will always be `gallery`. This property indicates UI that this flow needs to be shown in Flow gallery.
3. `azureml.promptflow.type`: value can be `chat`, `standard` or `evaluate`. This property identifies the type of your flow, and the UI will display different types of flows under separate tabs accordingly.
4. `azureml.promptflow.name`: the name of the flow which will be shown as the flow name in Flow gallery.
5. `azureml.promptflow.description`: the description of the flow which will be shown as flow description in Flow gallery.

### Register a model in a organization registry
Now you have all things ready, run below command to register the previous model to a organization registry. More details about [model creation](https://learn.microsoft.com/en-us/cli/azure/ml/model?view=azure-cli-latest#az-ml-model-create):
```
az ml model create -f model.yml --registry-name <organization-registry-name>
```

## How to locate a flow in the Flow gallery
- Open a workspace in the region which is supported by the organization registry. Your can find the regions supported by your registry in [this page](https://ml.azure.com/registries?tid=72f988bf-86f1-41af-91ab-2d7cd011db47).
- Click the `Create` button to open the Flow gallery, and you will find the flow registered before:

![organization examples in flow gallery](../../media/how-to-guides/share-example-in-org-registry/org_examples_in_flow_gallery.png)

1. `azureml.promptflow.type`: `evaluate` will be shown in the 'Evaluation' tab. Other values will be shown in the 'Flow' tab.
2. `azureml.promptflow.name`: shown as flow name in the flow card.
3. `azureml.promptflow.description`: shown as flow description in the flow card.
4. `readme.md`: click the `View detail` button will show the content in the `readme.md`.