# Quick Start (WIP)

This guide will walk you through the main user journey of prompt flow code-first experience. You will learn how to create and develop your first prompt flow, test and evaluate it, then deploy it to production.

## Prerequisites

1. A python environment, `python=3.8` is recommended.
2. Install `promptflow-sdk` and `prompt-flow-tools`.
```sh
pip install promptflow-sdk[builtins] prompt-flow-tools --extra-index-url https://azuremlsdktestpypi.azureedge.net/promptflow/
```
3. Get the sample flows. Clone the sample repo and see flows in folder `examples/flows`.
```sh
git clone https://github.com/microsoft/prompt-flow.git
```

## Create necessary connections

The connection helps securely store and manage secret keys or other sensitive credentials required for interacting with LLM and other external tools for example Azure Content Safety. See [Connections](https://promptflow.azurewebsites.net/concepts/concept-connections.html) for more details.

In this guide, we will use flow `web-classification` which uses connection `azure_open_ai_connection` inside, we need to set up the connection if we haven't added it before. Once created, the connection will be stored in local db and can be used in any flow.

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

Firstly we need a connection yaml file `connection.yaml`:
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/AzureOpenAIConnection.schema.json
name: azure_open_ai_connection
type: azure_open_ai
api_key: <test_key>
api_base: <test_base>
api_type: azure
api_version: <test_version>
```

Then we can use CLI command to create the connection.

```sh
pf connection create -f connection.yaml
```

More details can be found with `pf connection -h`

:::
:::{tab-item} SDK
:sync: SDK

```python
import promptflow as pf
from promptflow.sdk.entities import AzureOpenAIConnection

# client can help manage your runs and connections.
client = pf.PFClient()

try:
    conn_name = "azure_open_ai_connection"
    conn = client.connections.get(name=conn_name)
    print("using existing connection")
except:
    connection = AzureOpenAIConnection(
        name=conn_name,
        api_key="<test_key>",
        api_base="<test_base>",
        api_type="azure",
        api_version="<test_version>",
    )

    conn = client.connections.create_or_update(connection)
    print("successfully created connection")

print(conn)
```
:::

:::{tab-item} VSCode
:sync: VSCode
(WIP)
:::

::::

## Develope and test your flow
A flow in prompt flow serves as an executable workflow that streamlines the development of your LLM-based AI application. It provides a comprehensive framework for managing data flow and processing within your application. See [Flows](https://promptflow.azurewebsites.net/concepts/concept-flows.html) for more details.

In this guide, we use `web-classification` sample to walk you through the main user journey, it's a flow demonstrating multi-class classification with LLM. Given an url, it will classify the url into one web category with just a few shots, simple summarization and classification prompts.

You can test your flow with default inputs in `flow.dag.yaml`, then check the run status and outputs.

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

```sh
pf flow test --flow <path-to-the-samples>/web-classification
```

:::

:::{tab-item} VS Code Extension
:sync: VS Code Extension
(WIP)
:::

::::

## Create a new run

After the flow run successfully with a small set of data, you might want to test if it performs well in large set of data, you can run a batch test and choose some evaluation methods then check the metrics.

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

Create the run with flow and data, can add `--stream` to stream the run.
```sh
pf run create --flow <path-to-the-samples>/web-classification --data <path-to-the-samples>/web-classification/data.jsonl --stream
```

You can also name the run by specifying `--name my_first_run` in above command, otherwise the run name will be generated in a certain pattern which has timestamp inside.

With a run name, you can easily stream or view the run details using below commands:

```sh
pf run stream -n my_first_run  # same as "--stream" in command "run create"
pf run show-details -n my_first_run
```

You can also list the runs you have created.
```sh
pf run list --max-results 50
```

More details can be found with `pf run --help`

:::
:::{tab-item} SDK
:sync: SDK

```python
# Set flow path and run input data
flow = "<path-to-the-samples>/web-classification" # path to the flow directory
data="<path-to-the-samples>/web-classification/data.jsonl" # path to the data file

# create a run
base_run = pf.run(
    flow=flow,
    data=data,
)

# stream the run until it's finished
pf.stream(base_run)

# get the inputs/outputs details of a finished run.
details = pf.get_details(base_run)
details.head(10)
```

:::

:::{tab-item} VSCode
:sync: VSCode
(WIP)
:::

::::


## Evaluate your run

Now you can use an evaluation method to evaluate your flow. The evaluation methods are also flows which use Python or LLM etc., to calculate metrics like accuracy, relevance score.

In this guide, we use `classification-accuracy-eval` flow to evaluate. This is a flow illustrating how to evaluate the performance of a classification system. It involves comparing each prediction to the groundtruth and assigns a `Correct` or `Incorrect` grade, and aggregating the results to produce metrics such as `accuracy`, which reflects how good the system is at classifying the data.


### Run evaluation flow against run

::::{tab-set}

:::{tab-item} CLI
:sync: CLI
```sh
pf run create --flow <path-to-the-samples>/classification_accuracy_evaluation --data <path-to-the-samples>/web-classification/data.jsonl --column-mapping "groundtruth=${data.answer},prediction=${run.outputs.category}" --run my_first_run --stream
```

Same as the previous run, you can specify the evaluation run name with `--name my_first_eval_run` in above command.

With a run name, you can easily stream or view the run details using below commands:

```sh
pf run stream -n my_first_eval_run  # same as "--stream" in command "run create"
pf run show-details -n my_first_eval_run
pf run show-metrics -n my_first_eval_run
```

Since now you have two different runs `my_first_run` and `my_first_eval_run`, you can visualize the two runs at the same time with below command.

```sh
pf run visualize -n "my_first_run,my_first_eval_run"
```

:::

:::{tab-item} SDK
:sync: SDK

```python
# set eval flow path
eval_flow = "<path-to-the-samples>/classification-accuracy-eval"

# run the flow with exisiting run
eval_run = pf.run(
    flow=eval_flow,
    data="<path-to-the-samples>/web-classification/data.jsonl",  # path to the data file
    run=base_run,  # use run as the variant
    column_mapping={"groundtruth": "${data.answer}","prediction": "${run.outputs.category}"},  # map the url field from the data to the url input of the flow
)

# stream the run until it's finished
pf.stream(eval_run)

# get the inputs/outputs details of a finished run.
details = pf.get_details(eval_run)
details.head(10)

# view the metrics of the eval run
metrics = pf.get_metrics(eval_run)
print(json.dumps(metrics, indent=4))

# visualize both the base run and the eval run
pf.visualize([base_run, eval_run])

```

:::

:::{tab-item} VSCode
:sync: VSCode
(WIP)
:::

::::


### Create a run with different variant node

In this example, `web-classification`'s node `summarize_text_content` has two variants: `variant_0` and `variant_1`. The difference between them is the inputs parameters:

variant_0:
- inputs:
    - deployment_name: text-davinci-003
    - max_tokens: '128'
    - temperature: '0.2'
    - text: ${fetch_text_content_from_url.output}

variant_1:
- inputs:
    - deployment_name: text-davinci-003
    - max_tokens: '256'
    - temperature: '0.3'
    - text: ${fetch_text_content_from_url.output}


You can check the whole flow definistion at `<path-to-the-samples>/web-classification/flow.dag.yaml`.

Now we will create a variant run which uses node `summarize_text_content`'s variant `variant_1`.

::::{tab-set}

:::{tab-item} CLI
:sync: CLI

```sh
pf run create --flow <path-to-the-samples>/web-classification --data <path-to-the-samples>/web-classification/data.jsonl --variant "${summarize_text_content.variant_1}" --stream --name my_first_variant_run
```

:::

:::{tab-item} SDK
:sync: SDK

```python
# use the variant1 of the summarize_text_content node.
variant_run = pf.run(
    flow=flow,
    data=data,
    variant="${summarize_text_content.variant_1}",  # here we specify node "summarize_text_content" to use variant 1 verison.
)

pf.stream(variant_run)

details = pf.get_details(variant_run)
details.head(10)
```
:::

:::{tab-item} VS Code Extension
:sync: VS Code Extension
(WIP)
:::

::::


### Run evaluation flow against variant run


::::{tab-set}

:::{tab-item} CLI
:sync: CLI

```sh
pf run create --flow <path-to-the-samples>/classification_accuracy_evaluation --data <path-to-the-samples>/web-classification/data.jsonl --column-mapping "groundtruth=${data.answer},prediction=${run.outputs.category}" --run my_first_variant_run --stream --name my_second_eval_run
```

Visualize the two eval runs:
```sh
pf run visualize -n "my_first_eval_run,my_second_eval_run"
```
:::

:::{tab-item} SDK
:sync: SDK

```python
eval_flow = "<path-to-the-samples>/classification-accuracy-eval"

eval_run_variant = pf.run(
    flow=eval_flow,
    data="<path-to-the-samples>/web-classification/data.jsonl",  # path to the data file
    run=variant_run,  # use run as the variant
    column_mapping={"groundtruth": "${data.answer}","prediction": "${run.outputs.category}"},  # map the url field from the data to the url input of the flow
)

pf.stream(eval_run_variant)

details = pf.get_details(eval_run_variant)
details.head(10)

metrics = pf.get_metrics(eval_run_variant)
print(json.dumps(metrics, indent=4))

# visulize the two different evaluation runs
pf.visualize([eval_run, eval_run_variant])
```

:::

:::{tab-item} VS Code Extension
:sync: VS Code Extension
(WIP)
:::

::::

# Next steps

- Learn more about connections
- Learn more about flows


