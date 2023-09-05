# Flow in pipeline

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](https://aka.ms/azuremlexperimental).
:::

After you finalized a flow, besides deploying an online service, it is also possible that we need to use it as a part of offline data processing workflow. Promptflow provide a way to register a flow as a component so that you can use the flow in a pipeline in Azure Machine Learning.

You can check below documents for more information about related concepts:
- [What are Azure Machine Learning pipelines](https://learn.microsoft.com/en-us/azure/machine-learning/concept-ml-pipelines?view=azureml-api-2)
- [What is an Azure Machine Learning component](https://learn.microsoft.com/en-us/azure/machine-learning/concept-component?view=azureml-api-2)

:::{admonition} Important
This feature has not been released yet and you'll need to run below command first:
```bash
pip install azure-ai-ml==1.10.0a20230903001 --extra-index-url
https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/simple/
```
:::

## Register a flow as a component

Suppose the finalized flow is under `<your-flow-dir>`. With `promptflow-sdk`, you can register it as a component:

Note: Component registration has SDK experience only for now. CLI experience is WIP.

::::{tab-set}
:::{tab-item} SDK
```python
# Import required libraries
from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, load_component

# connect to a workspace in Azure Machine Learning
credential = DefaultAzureCredential()
ml_client = MLClient.from_config(credential=credential)

pf = PFClient(ml_client)

# default name is the the name of flow directory and default version is 1
flow_component = load_component(source="<your-flow-dag-path>")

# settings in run will be respected if load from run.yaml
flow_component_from_run = load_component(source="<your-flow-run-path>")

# attributes can also be override on loading
flow_component_with_param_override = load_component(
    source="<your-flow-dir>",
    params_override=[
        {
            "name": "updated_flow",
            "version": "2",
            "column_mapping": {
                "text": "${data.text}"
            },
            "connections": {
                "<node-name>": {
                    "connection": "azure_open_ai_connection",
                    "deployment_name": "text-davinci-003",
                }
            }
            "variant": "${<node-name>.<variant-name>}"
            "environment_variable": {
                "verbose": "true"
            },
            "is_deterministic": False,
        }
    ]
)

# a component with necessary input/output ports will be registered under the workspace
# version can also be specified on registration
registered_flow_component = ml_client.components.create_or_update(
    flow_component_with_param_override,
    version="3"
)
```
:::
::::

Valid parameters to override are as below:
- `name` and `version`: optional parameter to specify the name and version of the registered component. Default component name is the name of the flow directory; default version is `1`.
- `column_mapping`: the default column mapping to be used in flow run. All columns to map will be exposed as input parameters of the component and the value can be overwritten when using the component in a pipeline.
- `connections`: the default column mappings to be used in flow run. All connection settings will be exposed as input parameters of the component and the  be overwritten when using the component in a pipeline.
- `variant`: the variant to be used in flow run. Note that this value can't be overwritten in a pipeline.
- `environment_variables`: the extra environment variables to to be used in flow run
- `is_deterministic`: whether the registered component is deterministic, has a default value of `True`. Flow run will never be reused if it's set to `False`.

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
  flow_outputs:
    type: uri_folder
  run_outputs

jobs:
  data_transfer:
    component: "<another-component-spec>"
    type: command
    inputs:
      input_data: ${{parent.inputs.input_data}}
  flow_node:
    # registered flow component can be referred like regular components
    component: azureml:updated_flow:3
    type: parallel
    # node level run settings for flow node is similar to `ParallelComponent`
    logging_level: DEBUG
    max_concurrency_per_instance: 2
    inputs:
        # this can be either a URI jsonl file or a URI folder containing multiple jsonl files
        data: ${{parent.jobs.data_transfer.outputs.output_data}}
        # this is to overwrite column mapping
        text: ${data.text}
        # this is to overwrite connection settings
        connections.summarize_text_content.deployment_name: "azure_open_ai_connection"
        connections.summarize_text_content.connection: "text-davinci-003"
    outputs:
      flow_outputs: ${{parent.outputs.output_data}}
  anonymous_flow_node:
    # path to flow dag yaml and run yaml can be directly used here like regular components
    component: <your-flow-dag-path>
    type: parallel
    inputs:
        data: ${{parent.jobs.data_transfer.outputs.output_data}}

settings:
  default_compute: cpu-cluster
```
:::
:::{tab-item} SDK
```python
tsv2jsonl_component = load_component("<another-component-spec>")
anonymous_flow_component = load_component(source="<your-flow-dag-path>")

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
                "deployment_name": "azure_open_ai_connection",
                "connection": "text-davinci-003"
            },
        },
    )
    # node level run settings for flow node is similar to `ParallelComponent`
    flow_node.logging_level = "DEBUG"
    flow_node.max_concurrency_per_instance = 2

    anonymous_flow_node = anonymous_flow_component(
        data=data_transfer.outputs.output_data,
    )
    return flow_node.outputs

pipeline = pipeline_with_flow(
    input_data=Input(path="./data.tsv", type=AssetTypes.URI_FILE),
)

pipeline.settings.default_compute = "cpu-cluster"

created_job = ml_client.jobs.create_or_update(pipeline)
```
:::
::::

## Advanced: make flow signable

In some environment with high security requirement, customer may need to "sign" a component to grant it some extra permission.

Given that:
+ Signature will be calculated based on component snapshot
+ Flow component snapshot will be different from local if there are additional includes or variant in flow definition

Customer will need to make the flow signable with `mldesigner compile`:

::::{tab-set}
:::{tab-item} CLI

```bash
python -m pip install mldesigner[promptflow]

# additional includes will be copied to the new flow directory
# note that default variant will be used to update the flow dag yaml and compile with specific variant is not supported for now
mldesigner compile --source <your-flow-dag-path> --output <new-flow-directory>
```
:::
::::
