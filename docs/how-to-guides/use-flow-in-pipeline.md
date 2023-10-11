# Use flow in pipeline job

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

After you have developed and tested the flow in [init and test a flow](./init-and-test-a-flow.md), this guide will help you learn how to use a flow as a parallel component in a pipeline job on AzureML, so that you can integrate the created flow with existing pipelines and process a large amount of data.

:::{admonition} Pre-requirements
- Customer need to install the extension `ml>=2.21.0` to enable this feature in CLI and package `azure-ai-ml>=1.11.0` to enable this feature in SDK;
- Customer need to put `$schema` in the target `flow.dag.yaml` to enable this feature;
- Customer need to generate `flow.tools.json` for the target flow before below usage. Usually the generation can be done by `pf flow validate`.
:::

For more information about AzureML and component:
- [Install and set up the CLI(v2)](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-configure-cli?view=azureml-api-2&tabs=public)
- [Install and set up the SDK(v2)](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-ml-readme?view=azure-python)
- [What is a pipeline](https://learn.microsoft.com/en-us/azure/machine-learning/concept-ml-pipelines?view=azureml-api-2)
- [What is a component](https://learn.microsoft.com/en-us/azure/machine-learning/concept-component?view=azureml-api-2)

## Register a flow as a component

Customer can register a flow as a component with either CLI or SDK. 

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
# Register flow as a component
# Default component name will be the name of flow folder, which is not a valid component name, so we override it here; default version will be "1"
az ml component create --file standard/web-classification/flow.dag.yaml --set name=web_classification

# Register flow as a component with parameters override
az ml component create --file standard/web-classification/flow.dag.yaml --version 2 --set name=web_classification_updated
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from azure.ai.ml import MLClient, load_component

ml_client = MLClient()

# Register flow as a component
# Default component name will be the name of flow folder, which is web-classification here; default version will be "1"
flow_component = load_component("standard/web-classification/flow.dag.yaml")
ml_client.components.create_or_update(flow_component)

# Register flow as a component with parameters override
ml_client.components.create_or_update(
    "standard/web-classification/flow.dag.yaml",
    version="2",
    params_override=[
        {"name": "web-classification_updated"}
    ]
)
```

:::

::::

After registered a flow as a component, they can be referred in a pipeline job like [regular registered components](https://github.com/Azure/azureml-examples/tree/main/cli/jobs/pipelines-with-components/basics/1b_e2e_registered_components).

## Directly use a flow in a pipeline job

Besides explicitly registering a flow as a component, customer can also directly use flow in a pipeline job:
- [CLI sample](https://github.com/Azure/azureml-examples/tree/zhangxingzhi/flow-in-pipeline/cli/jobs/pipelines-with-components/flow_in_pipeline/1a_flow_in_pipeline)
- [SDK sample](https://github.com/Azure/azureml-examples/blob/zhangxingzhi/flow-in-pipeline/sdk/python/jobs/pipelines/1l_flow_in_pipeline/flow_in_pipeline.ipynb)
