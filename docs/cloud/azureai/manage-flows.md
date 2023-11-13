# Manage flows

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

This documentation will walk you through how to manage your flow with CLI and SDK on [Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2). 
The flow examples in this guide come from [examples/flows/standard](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard)

In general:
- For `CLI`, you can run `pfazure flow --help` in the terminal to see help messages.
- For `SDK`, you can refer to [Promptflow Python Library Reference](../reference/python-library-reference/promptflow.md) and check `promptflow.azure.PFClient.flows` for more flow operations.

Let's take a look at the following topics:

- [Manage flows](#manage-flows)
  - [Create a flow](#create-a-flow)


## Create a flow

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

To create a run against bulk inputs, you can write the following YAML file.

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json
flow: ../web_classification
data: ../webClassification1.jsonl
column_mapping:
   url: "${data.url}"
variant: ${summarize_text_content.variant_0}
```

To create a run against existing run, you can write the following YAML file.

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json
flow: ../classification_accuracy_evaluation
data: ../webClassification1.jsonl
column_mapping:
   groundtruth: "${data.answer}"
   prediction: "${run.outputs.category}"
run: <existing-flow-run-name>
```

Reference [here](https://aka.ms/pf/column-mapping) for detailed information for column mapping.
You can find additional information about flow yaml schema in [Run YAML Schema](../reference/run-yaml-schema-reference.md).

After preparing the yaml file, use the CLI command below to create them:

```bash
# create the flow run
pf run create -f <path-to-flow-run> 

# create the flow run and stream output
pf run create -f <path-to-flow-run> --stream
```

The expected result is as follows if the run is created successfully.

![img](../media/how-to-guides/run_create.png)
:::


:::{tab-item} SDK
:sync: SDK
Using SDK, create `Run` object and submit it with `PFClient`. The following code snippet shows how to import the required class and create the run:

```python
from promptflow import PFClient
from promptflow.entities import Run

# Get a pf client to manage runs
pf = PFClient()

# Initialize an Run object
run = Run( 
    flow="<path-to-local-flow>",
    # run flow against local data or existing run, only one of data & run can be specified. 
    data="<path-to-data>",
    run="<existing-run-name>",
    column_mapping={"url": "${data.url}"},
    variant="${summarize_text_content.variant_0}"
)

# Create the run
result = pf.runs.create_or_update(run)
print(result)

```
:::

::::



