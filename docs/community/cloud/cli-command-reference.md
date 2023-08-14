# CLI reference: pfazure

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](https://aka.ms/azuremlexperimental).
:::

Manage prompt flow resources on Azure with the prompt flow CLI.

| Command | Description |
| --- | --- |
| [pfazure run](#pfazure-run) | Manage runs. |

## pfazure run

Manage prompt flow runs.

| Command | Description |
| --- | --- |
| [pfazure run create](#pfazure-run-create) | Create a run. |
| [pfazure run list](#pfazure-run-list) | List runs in a workspace. |
| [pfazure run show](#pfazure-run-show) | Show details for a run. |
| [pfazure run stream](#pfazure-run-stream) | Stream run logs to the console. |
| [pfazure run show-details](#pfazure-run-show-details) | Show a run details. |
| [pfazure run show-metrics](#pfazure-run-show-metrics) | Show run metrics. |
| [pfazure run visualize](#pfazure-run-visualize) | Visualize a run. |

### pfazure run create

Create a run.

```bash
pfazure run create [--file]
                   [--flow]
                   [--data]
                   [--column-mapping]
                   [--run]
                   [--variant]
                   [--stream]
                   [--environment-variables]
                   [--connections]
                   [--set]
                   [--subscription]
                   [--resource-group]
                   [--workspace-name]
```

#### Parameters

`--file -f`

Local path to the YAML file containing the prompt flow run specification; can be overrided by other parameters. Reference [here](https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json) for YAML schema.

`--flow`

Local path to the flow directory.

`--data`

Local path to the data file.

`--column-mapping`

Inputs column mapping, use `${data.xx}` to refer to data file columns, use `${run.inputs.xx}` and `${run.outputs.xx}` to refer to run inputs/outputs columns.

`--run`

Referenced flow run name. For example, you can run an evaluation flow against an existing run. For example, "pfazure run create --flow evaluation_flow_dir --run existing_bulk_run".

`--variant`

Node & variant name in format of `${node_name.variant_name}`.

`--stream -s`

Indicates whether to stream the run's logs to the console.  
default value: False

`--environment-variables`

Environment variables to set by specifying a property path and value. Example:
`--environment-variable key1='${my_connection.api_key}' key2='value2'`. The value reference
to connection keys will be resolved to the actual value, and all environment variables
specified will be set into os.environ.

`--connections`

Overwrite node level connections with provided value.
Example: `--connections node1.connection=test_llm_connection node1.deployment_name=gpt-35-turbo`

`--set`

Update an object by specifying a property path and value to set.
Example: `--set property1.property2=<value>`.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run list

List runs in a workspace.

```bash
pfazure run list [--archived-only]
                 [--include-archived]
                 [--max-results]
                 [--subscription]
                 [--resource-group]
                 [--workspace-name]
```

#### Parameters

`--archived-only`

List archived runs only.  
default value: False

`--include-archived`

List archived runs and active runs.  
default value: False

`--max-results -r`

Max number of results to return. Default is 50, upper bound is 100.  
default value: 50

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run show

Show details for a run.

```bash
pfazure run show --name
                 [--subscription]
                 [--resource-group]
                 [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run stream

Stream run logs to the console.

```bash
pfazure run stream --name
                   [--subscription]
                   [--resource-group]
                   [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run show-details

Show a run details.

```bash
pfazure run show-details --name
                         [--subscription]
                         [--resource-group]
                         [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run show-metrics

Show run metrics.

```bash
pfazure run show-metrics --name
                         [--subscription]
                         [--resource-group]
                         [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.

### pfazure run visualize

Visualize a run.

```bash
pfazure run visualize --name
                      [--subscription]
                      [--resource-group]
                      [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when pass run id.

`--resource-group -g`

Resource group name, required when pass run id.

`--workspace-name -w`

Workspace name, required when pass run id.