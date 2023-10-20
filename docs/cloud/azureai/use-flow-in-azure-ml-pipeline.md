# Use flow in Azure ML pipeline job

After you have developed and tested the flow in [init and test a flow](../../how-to-guides/init-and-test-a-flow.md), this guide will help you learn how to use a flow as a parallel component in a pipeline job on AzureML, so that you can integrate the created flow with existing pipelines and process a large amount of data.

:::{admonition} Pre-requirements
- Customer need to install the extension `ml>=2.21.0` to enable this feature in CLI and package `azure-ai-ml>=1.11.0` to enable this feature in SDK;
- Customer need to put `$schema` in the target `flow.dag.yaml` to enable this feature;
  - `flow.dag.yaml`: `$schema`: `https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json`
  - `run.yaml`: `$schema`: `https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json`
- Customer need to generate `flow.tools.json` for the target flow before below usage. The generation can be done by `pf flow validate`.
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
flow_component = load_component("standard/web-classification/flow.dag.yaml")
# Default component name will be the name of flow folder, which is not a valid component name, so we override it here; default version will be "1"
flow_component.name = "web_classification"
ml_client.components.create_or_update(flow_component)

# Register flow as a component with parameters override
ml_client.components.create_or_update(
    "standard/web-classification/flow.dag.yaml",
    version="2",
    params_override=[
        {"name": "web_classification_updated"}
    ]
)
```

:::

::::

After registered a flow as a component, they can be referred in a pipeline job like [regular registered components](https://github.com/Azure/azureml-examples/tree/main/cli/jobs/pipelines-with-components/basics/1b_e2e_registered_components).

## Directly use a flow in a pipeline job

Besides explicitly registering a flow as a component, customer can also directly use flow in a pipeline job:
- [CLI example](https://github.com/Azure/azureml-examples/tree/main/cli/jobs/pipelines-with-components/pipeline_job_with_flow_as_component)
- [SDK example](https://github.com/Azure/azureml-examples/tree/main/sdk/python/jobs/pipelines/1l_flow_in_pipeline)

All connections and flow inputs will be exposed as input parameters of the component. Default value can be provided in flow/run definition; they can also be set/overwrite on job submission:

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```yaml
...
jobs:
  flow_node:
    type: parallel
    component: standard/web-classification/flow.dag.yaml
    inputs:
      data: ${{parent.inputs.web_classification_input}}
      url: "${data.url}"
      connections.summarize_text_content.connection: azure_open_ai_connection
      connections.summarize_text_content.deployment_name: text-davinci-003
...
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from azure.ai.ml import dsl

ml_client = MLClient()

# Register flow as a component
flow_component = load_component("standard/web-classification/flow.dag.yaml")
data_input = Input(path="standard/web-classification/data.jsonl", type=AssetTypes.URI_FILE)

@dsl.pipeline
def pipeline_func_with_flow(data):
    flow_node = flow_component(
        data=data,
        url="${data.url}",
        connections={
            "summarize_text_content": {
                "connection": "azure_open_ai_connection",
                "deployment_name": "text-davinci-003",
            },
        },
    )
    flow_node.compute = "cpu-cluster"

pipeline_with_flow = pipeline_func_with_flow(data=data_input)

ml_client.jobs.create_or_update(pipeline_with_flow)
```

:::

::::
