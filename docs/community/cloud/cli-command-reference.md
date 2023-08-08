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
                   [--subscription]
                   [--resource-group]
                   [--workspace-name]
```

#### Parameters

`--file -f`

Local path to the YAML file containing the prompt flow run specification; can be overrided by other parameters.

`--flow`

Local path to the flow directory.

`--data`

Local path to the data file.

`--column-mapping`

Inputs column mapping, use `${data.xx}` to refer to data file columns, use `${run.inputs.xx}` and `${run.outputs.xx}` to refer to run inputs/outputs columns.

`--run`

Referenced flow run name.

`--variant`

Node & variant name in format of `${node_name.variant_name}`.

`--stream -s`

Indicates whether to stream the run's logs to the console.  
default value: False

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
