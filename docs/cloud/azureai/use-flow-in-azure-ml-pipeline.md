# Use flow in Azure ML pipeline job
In practical scenarios, flows fulfill various functions. For example, consider an offline flow specifically designed to assess the relevance score for communication sessions between humans and agents. This flow is triggered nightly and processes a substantial amount of session data. In such a context, Parallel component and AzureML pipeline emerge as the optimal choices for handling large-scale, highly resilient, and efficient offline batch requirements.

Once you’ve developed and thoroughly tested your flow, this guide will walk you through utilizing your flow as a parallel component within an AzureML pipeline job.

:::{admonition} Pre-requirements
To enable this feature, customer need to:
1. install related CLI or package:
    1. For CLI, please [install Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) first and then install the extension `ml>=2.22.0` via `az extension add -n ml`;
    2. For SDK, please install package `azure-ai-ml>=1.12.0` via `pip install azure-ai-ml>=1.12.0` or `pip install promptflow[azure]`;
2. ensure that there is a `$schema` in the target source:
    1. `flow.dag.yaml`: `$schema`: `https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json`
    2. `run.yaml`: `$schema`: `https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json`
3. ensure that metadata has been generated and is up-to-date:
    1. `<my-flow-directory>/.promptflow/flow.tools.json` should exist;
    2. customer may update the file via `pf flow validate --source <my-flow-directory>`.

:::

To explore an executable end-to-end example of running sample flow within Azure ML workspace, you can refer to this tutorial notebook: [run flow with pipeline](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/run-flow-with-pipeline/pipeline.ipynb)

For more information about AzureML and component:
- [What is Azure CLI](https://learn.microsoft.com/en-us/cli/azure/what-is-azure-cli)
- [Install and set up the CLI(v2)](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-configure-cli)
- [Install and set up the SDK(v2)](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-ml-readme)
- [What is a pipeline](https://learn.microsoft.com/en-us/azure/machine-learning/concept-ml-pipelines)
- [What is a component](https://learn.microsoft.com/en-us/azure/machine-learning/concept-component)
- [How to use parallel job in pipeline (V2)](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-parallel-job-in-pipeline)

## Register a flow as a component

Suppose there has been a flow and its `flow.dag.yaml` is as below:
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
environment:
  python_requirements_txt: requirements.txt
inputs:
  text:
    type: string
    default: Hello World!
outputs:
  output:
    type: string
    reference: ${llm.output}
nodes:
- name: hello_prompt
  type: prompt
  source:
    type: code
    path: hello.jinja2
  inputs:
    text: ${inputs.text}
- name: llm
  type: python
  source:
    type: code
    path: hello.py
  inputs:
    prompt: ${hello_prompt.output}
    deployment_name: text-davinci-003
    max_tokens: "120"
```

Customer can register a flow as a component with either CLI or SDK:

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
# Register flow as a component
az ml component create --file \<my-flow-directory\>/flow.dag.yaml

# Register flow as a component and specify its name and version
# Default component name will be the name of flow folder, which can be invalid as a component name; default version will be "1"
az ml component create --file \<my-flow-directory\>/flow.dag.yaml --version 3 --set name=basic_updated
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from azure.ai.ml import MLClient, load_component

ml_client = MLClient()

# Register flow as a component
flow_component = load_component("<my-flow-directory>/flow.dag.yaml")
ml_client.components.create_or_update(flow_component)

# Register flow as a component and specify its name and version
# Default component name will be the name of flow folder, which can be invalid as a component name; default version will be "1"
flow_component.name = "basic_updated"
ml_client.components.create_or_update(flow_component, version="3")
```

:::

::::

The generated component will be a parallel component, whose definition will be as below:

```yaml
name: basic
version: 1
display_name: basic
is_deterministic: True
type: parallel
inputs:
  data:
    type: uri_folder
    optional: False
  run_outputs:
    type: uri_folder
    optional: True
  text:
    type: string
    optional: False
    default: Hello World!
outputs:
  flow_outputs:
    type: uri_folder
  debug_info:
    type: uri_folder
...
```

Besides the fixed input/output ports, all connections and flow inputs will be exposed as input parameters of the component. Default value can be provided in flow/run definition; they can also be set/overwrite on job submission. Full description of ports can be seen in section [Component ports and run settings](#component-ports-and-run-settings).

## Use a flow in a pipeline job

After registered a flow as a component, they can be referred in a pipeline job like [regular registered components](https://github.com/Azure/azureml-examples/tree/main/cli/jobs/pipelines-with-components/basics/1b_e2e_registered_components). Customer may also directly use a flow in a pipeline job, then anonymous components will be created on job submission.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```yaml
...
inputs:
  basic_input:
    type: uri_file
    path: <path-to-data>
compute: azureml:cpu-cluster
jobs:
  flow_from_registered:
    type: parallel
    component: azureml:my_flow_component:1
    inputs:
      data: ${{parent.inputs.basic_input}}
      text: "${data.text}"
  flow_from_dag:
    type: parallel
    component: <path-to-flow-dag-yaml>
    inputs:
      data: ${{parent.inputs.basic_input}}
      text: "${data.text}"
  flow_from_run:
    type: parallel
    component: <path-to-run-yaml>
    inputs:
      data: ${{parent.inputs.basic_input}}
      text: "${data.text}"
...
```

Pipeline job can be submitted via `az ml job create --file pipeline.yml`.

Full example can be found [here](https://github.com/Azure/azureml-examples/tree/main/cli/jobs/pipelines-with-components/pipeline_job_with_flow_as_component).

:::

:::{tab-item} SDK
:sync: SDK

```python
from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, load_component, Input
from azure.ai.ml.dsl import pipeline

credential = DefaultAzureCredential()
ml_client = MLClient.from_config(credential=credential)
data_input = Input(path="<path-to-data>", type='uri_file')

flow_component_from_registered = ml_client.components.get("my_flow_component", "1")
flow_component_from_dag = load_component("<path-to-flow-dag-yaml>")
flow_component_from_run = load_component("<path-to-run-yaml>")

@pipeline
def pipeline_func_with_flow(basic_input):
    flow_from_registered = flow_component_from_registered(
        data=data,
        text="${data.text}",
    )
    flow_from_dag = flow_component_from_dag(
        data=data,
        text="${data.text}",
    )
    flow_from_run = flow_component_from_run(
        data=data,
        text="${data.text}",
    )

pipeline_with_flow = pipeline_func_with_flow(basic_input=data_input)
pipeline_with_flow.compute = "cpu-cluster"

pipeline_job = ml_client.jobs.create_or_update(pipeline_with_flow)
ml_client.jobs.stream(pipeline_job.name)
```

Full example can be found [here](https://github.com/Azure/azureml-examples/tree/main/sdk/python/jobs/pipelines/1l_flow_in_pipeline).

:::

::::

Like regular parallel components, customer may specify run settings for them in a pipeline job. Some regularly used run settings have been listed in section [Component ports and run settings](#component-ports-and-run-settings); customer may also refer to [the official document of parallel component](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-parallel-job-in-pipeline?view=azureml-api-2&tabs=cliv2) for more details:

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```yaml
...
jobs:
  flow_node:
    type: parallel
    component: <path-to-complicated-run-yaml>
    compute: azureml:cpu-cluster
    instance_count: 2
    max_concurrency_per_instance: 2
    mini_batch_error_threshold: 5
    retry_settings:
      max_retries: 3
      timeout: 30
    inputs:
      data: ${{parent.inputs.data}}
      url: "${data.url}"
      connections.summarize_text_content.connection: azure_open_ai_connection
      connections.summarize_text_content.deployment_name: text-davinci-003
      environment_variables.AZURE_OPENAI_API_KEY: ${my_connection.api_key}
      environment_variables.AZURE_OPENAI_API_BASE: ${my_connection.api_base}
...
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, load_component, Input
from azure.ai.ml.dsl import pipeline
from azure.ai.ml.entities import RetrySettings

credential = DefaultAzureCredential()
ml_client = MLClient.from_config(credential=credential)
data_input = Input(path="<path-to-data>", type='uri_file')

# Load flow as a component
flow_component = load_component("<path-to-complicated-run-yaml>")

@pipeline
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
        environment_variables={
            "AZURE_OPENAI_API_KEY": "${my_connection.api_key}",
            "AZURE_OPENAI_API_BASE": "${my_connection.api_base}",
        }
    )
    flow_node.compute = "cpu-cluster"
    flow_node.instance_count = 2
    flow_node.max_concurrency_per_instance = 2
    flow_node.mini_batch_error_threshold = 5
    flow_node.retry_settings = RetrySettings(timeout=30, max_retries=5)

pipeline_with_flow = pipeline_func_with_flow(data=data_input)

pipeline_job = ml_client.jobs.create_or_update(pipeline_with_flow)
ml_client.jobs.stream(pipeline_job.name)
```

:::

::::

## Environment of the component

By default, the environment of the created component will be based on the latest promptflow runtime image. If customer has [specified python requirement file](../../reference/flow-yaml-schema-reference.md) in `flow.dag.yaml`, they will be applied to the environment automatically:

``` yaml
...
environment:
  python_requirements_txt: requirements.txt
```

If customer want to use an existing Azure ML environment or define the environment in Azure ML style, they can define it in `run.yaml` like below:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json
flow: <my-flow-directory>
azureml:
  environment: azureml:my-environment:1
```

For more details about the supported format of Azure ML environment, please refer to [this doc](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-environments-v2?view=azureml-api-2&tabs=cli).

## Difference across flow in prompt flow and pipeline job

In prompt flow, flow runs on compute session, which is designed for prompt flow; while in pipeline job, flow runs on different types of compute, and usually compute cluster.

Given above, if your flow has logic relying on identity or environment variable, please be aware of this difference as you might run into some unexpected error(s) when the flow runs in pipeline job, and you might need some extra configurations to make it work.

## Component ports and run settings

### Input ports

| key         | source | type                   | description                                                  |
| ----------- | ------ | ---------------------- | ------------------------------------------------------------ |
| data        | fixed  | uri_folder or uri_file | required; to pass in input data. Supported format includes [`mltable`](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-mltable?view=azureml-api-2&tabs=cli#authoring-mltable-files) and list of jsonl files. |
| run_outputs | fixed  | uri_folder             | optional; to pass in output of a standard flow for [an evaluation flow](../../how-to-guides/develop-a-dag-flow/develop-evaluation-flow.md). Should be linked to a `flow_outputs` of a previous flow node in the pipeline. |

### Output ports

| key          | source | type       | description                                                  |
| ------------ | ------ | ---------- | ------------------------------------------------------------ |
| flow_outputs | fixed  | uri_folder | an uri_folder with 1 or more jsonl files containing outputs of the flow runs |
| debug_info   | fixed  | uri_folder | an uri_folder containing debug information of the flow run, e.g., run logs |

### Parameters

| key                                                 | source                                           | type   | description                                                  |
| --------------------------------------------------- | ------------------------------------------------ | ------ | ------------------------------------------------------------ |
| \<flow-input-name\>                                 | from flow inputs                                 | string | default value will be inherited from flow inputs; used to override [column mapping](../../how-to-guides/run-and-evaluate-a-flow/use-column-mapping.md) for flow inputs. |
| connections.\<node-name\>.connection                | from nodes of built-in LLM tools                 | string | default value will be current value defined in `flow.dag.yaml` or `run.yaml`; to override used connections of corresponding nodes. Connection should exist in current workspace. |
| connections.\<node-name\>.deployment_name           | from nodes of built-in LLM tools                 | string | default value will be current value defined in `flow.dag.yaml` or `run.yaml`; to override target deployment names of corresponding nodes. Deployment should be available with provided connection. |
| connections.\<node-name\>.\<node-input-key\>        | from nodes with `Connection` inputs              | string | default value will be current value defined in `flow.dag.yaml` or `run.yaml`; to override used connections of corresponding nodes. Connection should exist in current workspace. |
| environment_variables.\<environment-variable-name\> | from environment variables defined in `run.yaml` | string | default value will be the current value defined in `run.yaml`; to override environment variables during flow run, e.g. AZURE_OPENAI_API_KEY. Note that you can refer to workspace connections with expressions like `{my_connection.api_key}`. |

### Run settings

| key                          | type                    | Description                                                  |
| ---------------------------- | ----------------------- | ------------------------------------------------------------ |
| instance_count               | integer                 | The number of nodes to use for the job. Default value is 1.  |
| max_concurrency_per_instance | integer                 | The number of processors on each node.                       |
| mini_batch_error_threshold   | integer                 | Define the number of failed mini batches that could be ignored in this parallel job. If the count of failed mini-batch is higher than this threshold, the parallel job will be marked as failed.<br/><br/>Mini-batch is marked as failed if:<br/>- the count of return from run() is less than mini-batch input count.<br/>- catch exceptions in custom run() code.<br/><br/>"-1" is the default number, which means to ignore all failed mini-batch during parallel job. |
| retry_settings.max_retries   | integer                 | Define the number of retries when mini-batch is failed or timeout. If all retries are failed, the mini-batch will be marked as failed to be counted by `mini_batch_error_threshold` calculation. |
| retry_settings.timeout       | integer                 | Define the timeout in seconds for executing custom run() function. If the execution time is higher than this threshold, the mini-batch will be aborted, and marked as a failed mini-batch to trigger retry. |
| logging_level                | INFO, WARNING, or DEBUG | Define which level of logs will be dumped to user log files. |

Check [the official document of parallel component](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-parallel-job-in-pipeline?view=azureml-api-2&tabs=cliv2) for more run settings.
