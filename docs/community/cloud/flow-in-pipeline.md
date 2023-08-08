# Flow in pipeline

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](https://aka.ms/azuremlexperimental).
:::

After you finalized a flow, besides deploying an online service, it is also possible that we need to use it as a part of offline data processing workflow. Promptflow provide a way to register a flow as a component so that you can use the flow in a pipeline in Azure Machine Learning.

You can check below documents for more information about related concepts:
- [What are Azure Machine Learning pipelines](https://learn.microsoft.com/en-us/azure/machine-learning/concept-ml-pipelines?view=azureml-api-2)
- [What is an Azure Machine Learning component](https://learn.microsoft.com/en-us/azure/machine-learning/concept-component?view=azureml-api-2)


## Register a flow as a component

Suppose the finalized flow is under `<your-flow-dir>`. With `promptflow-sdk`, you can register it as a component:

Note: Component registration has SDK experience only for now. CLI experience is WIP.

::::{tab-set}
:::{tab-item} SDK
```python
# Import required libraries
from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient
import promptflow.azure as pf

# connect to a workspace in Azure Machine Learning
credential = DefaultAzureCredential()
ml_client = MLClient.from_config(credential=credential)

pf.configure(ml_client)
flow_component = pf.load_as_component(
    source="<your-flow-dir>",
    columns_mapping={
        "groundtruth": "${data.answer}",
        "prediction": "${run.outputs.category}",
    },
    component_type="parallel"
)
```
:::
::::

Then a component with necessary input/output ports will be registered under the workspace.

Related parameters are as below:
- `source`: the path to the flow to register.
- `columns_mapping`: the default column mappings to be used in flow run. The value can be overwritten when using the component in a pipeline.
- `component_type`: specify the target component type to register as. `parallel` is the only valid value for now.
  - `parallel`: register flow as a ParallelComponent, which allow flow runs in multiple compute instances in parallel to accelerate the data processing.
- `variant`: the variant to be used in flow run. Note that this value can't be overwritten in a pipeline.
- `environment_variables`: the extra environment variablesto to be used in flow run
- `is_deterministic`: whether the registered component is deterministic, has a default value of `True`. Flow run will never be reused if it's set to `False`.
- `name` and `version`: optional parameter to specify the name and version of the registered component. Neither or both of them should be provided. If neither are provided, registered component will have a fixed component name and a hash-based version; If both are provided, server-side will try to register the component with provided name and version, and will fail if a component of the same name and version has already been registered.

## Use a flow in a pipeline

After registered a flow as a component, you can use it in a pipeline in Azure Machine Learning like regular components in SDK. You can also use it along with other components:

::::{tab-set}
:::{tab-item} CLI
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/pipelineJob.schema.json
name: pipeline_with_flow
inputs:
  input_data:
    type: uri_file
    path: ./data.tsv
outputs:
  output_data:
    type: uri_folder

jobs:
  data_transfer:
    component: "<another-component-spec>"
    type: command
    inputs:
      input_data: ${{parent.inputs.input_data}}
  flow_node:
    component: azureml:<registered-component-name>:<registered-component-version>
    type: parallel
    # node level run settings for flow node is similar to `ParallelComponent`
    logging_level: DEBUG
    max_concurrency_per_instance: 2
    inputs:
        # this can be either a URI jsonl file or a URI folder containing multiple jsonl files
        data: ${{parent.jobs.data_transfer.outputs.output_data}}
        # this is to overwrite connection settings
        connections.summarize_text_content.deployment_name: "another_deployment_name"
        connections.summarize_text_content.connection: "another_connection"
        groundtruth: Channel
    outputs:
      output_data: ${{parent.outputs.output_data}}

settings:
  default_compute: cpu-cluster
```
:::
:::{tab-item} SDK
```python
tsv2jsonl_component = load_component("<another-component-spec>")

@dsl.pipeline
def pipeline_with_flow(input_data):
    data_transfer = tsv2jsonl_component(input_data=input_data)

    flow_node = flow_component(
        # this can be either a URI jsonl file or a URI folder containing multiple jsonl files
        data=data_transfer.outputs.output_data,
        # columns_mapping can be overwritten here.
        groundtruth="${data.expected}",
        # this is to overwrite connection settings
        connections={
            # this is to overwrite connection related settings for a LLM node
            # "summarize_text_content" is the node name
            "summarize_text_content": {
                "deployment_name": "another_deployment_name",
                "connection": "another_connection"
            },
        },
    )
    # node level run settings for flow node is similar to `ParallelComponent`
    flow_node.logging_level = "DEBUG"
    flow_node.max_concurrency_per_instance = 2
    return flow_node.outputs

pipeline = pipeline_with_flow(
    input_data=Input(path="./data.tsv", type=AssetTypes.URI_FILE),
)

pipeline.settings.default_compute = "cpu-cluster"

created_job = ml_client.jobs.create_or_update(pipeline)
```
:::
::::

Samples can also be found in [our sample repo](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/flow-in-pipeline)

## Download the flow component

Flow will be registered as a component in a specific workspace by default. If you want to use it in another workspace, you can download the registered component. 

Downloaded component includes a component spec and a folder including a snapshot of the flow.

This feature is still WIP.