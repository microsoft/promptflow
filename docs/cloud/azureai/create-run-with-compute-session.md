# Create run with compute session

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../../how-to-guides/faq.md#stable-vs-experimental).
:::

A prompt flow compute session provides computing resources that are required for the application to run, including a Docker image that contains all necessary dependency packages. This reliable and scalable compute session environment enables prompt flow to efficiently execute its tasks and functions for a seamless user experience.

If you're a new user, we recommend that you use the compute session (preview). You can easily customize the environment by adding packages in the requirements.txt file in flow.dag.yaml in the flow folder.

## Create a run with compute session


::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pfazure run create --flow path/to/flow --data path/to/data --stream
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from promptflow.azure import PFClient


pf = PFClient(
    credential=credential,
    subscription_id="<SUBSCRIPTION_ID>",  # this will look like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    resource_group_name="<RESOURCE_GROUP>",
    workspace_name="<AML_WORKSPACE_NAME>",
)
pf.run(
    flow=flow,
    data=data,
)
```

:::
::::

## Specify pip requirements for compute session

If `requirements.txt` exists in the same folder with `flow.dag.yaml`.
The dependencies in it will be automatically installed for compute session.

You can also specify which requirements file to use in `flow.dag.yaml` like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
environment:
  python_requirements_txt: path/to/requirement/file
...
```

Reference [Flow YAML Schema](../../reference/flow-yaml-schema-reference.md) for details.

## Customize compute session

In compute session case, you can also specify the instance type, if you don't specify the instance type, Azure Machine Learning chooses an instance type (VM size) based on factors like quota, cost, performance and disk size, learn more about [serverless compute](https://docs.microsoft.com/en-us/azure/machine-learning/how-to-use-serverless-compute).

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json
flow: <path_to_flow>
data: <path_to_flow>/data.jsonl

column_mapping:
  url: ${data.url}

# define instance type only work for compute session.
resources:
  instance_type: <instance_type>
```

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pfazure run create --file run.yml
```

:::

:::{tab-item} SDK
:sync: SDK

```python
from promptflow.client import load_run

run = load_run(source="run.yml")
pf = PFClient(
    credential=credential,
    subscription_id="<SUBSCRIPTION_ID>",  # this will look like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    resource_group_name="<RESOURCE_GROUP>",
    workspace_name="<AML_WORKSPACE_NAME>",
)
pf.runs.create_or_update(
    run=run
)
```
:::
::::

## Next steps

- Try the example [here](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/run-management/cloud-run-management.ipynb).
