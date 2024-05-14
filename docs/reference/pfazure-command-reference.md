# pfazure

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../how-to-guides/faq.md#stable-vs-experimental).
:::

Manage prompt flow resources on Azure with the prompt flow CLI.

| Command | Description |
| --- | --- |
| [pfazure flow](#pfazure-flow) | Manage flows. |
| [pfazure run](#pfazure-run) | Manage runs. |


## pfazure flow

Manage flows.

| Command | Description |
| --- | --- |
| [pfazure flow create](#pfazure-flow-create) | Create a flow. |
| [pfazure flow update](#pfazure-flow-update) | Update a flow. |
| [pfazure flow list](#pfazure-flow-list) | List flows in a workspace. |


### pfazure flow create

Create a flow in Azure AI from a local flow folder.

```bash
pfazure flow create [--flow]
                    [--set]
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Parameters

`--flow`

Local path to the flow directory.

`--set`

Update an object by specifying a property path and value to set.
- `display_name`: Flow display name that will be created in remote. Default to be flow folder name + timestamp if not specified. e.g. "--set display_name=\<display_name\>".
- `type`: Flow type. Default to be "standard" if not specified. Available types are: "standard", "evaluation", "chat". e.g. "--set type=\<type\>".
- `description`: Flow description. e.g. "--set description=\<description\>."
- `tags`: Flow tags. e.g. "--set tags.key1=value1 tags.key2=value2."

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.



### pfazure flow update

Update a flow's metadata, such as `display name`, `description` and `tags`.

```bash
pfazure flow update --flow
                    [--set]
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Parameters

`--flow`

The flow name on azure. It's a guid that can be found from 2 ways:
- After creating a flow to azure, it can be found in the printed message in "name" attribute.
- Open a flow in azure portal, the guid is in the url. e.g. https://ml.azure.com/prompts/flow/{workspace-id}/{flow-name}/xxx


`--set`

Update an object by specifying a property path and value to set.
- `display_name`: Flow display name. e.g. "--set display_name=\<display_name\>".
- `description`: Flow description. e.g. "--set description=\<description\>."
- `tags`: Flow tags. e.g. "--set tags.key1=value1 tags.key2=value2."

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.


### pfazure flow list

List remote flows on Azure AI.

```bash
pfazure flow list [--max-results]
                  [--include-others]
                  [--type]
                  [--output]
                  [--archived-only]
                  [--include-archived]
                  [--subscription]
                  [--resource-group]
                  [--workspace-name]
                  [--output]
```

#### Parameters

`--max-results -r`

Max number of results to return. Default is 50, upper bound is 100.

`--include-others`

Include flows created by other owners. By default only flows created by the current user are returned.

`--type`

Filter flows by type. Available types are: "standard", "evaluation", "chat".

`--archived-only`

List archived flows only.

`--include-archived`

List archived flows and active flows.

`--output -o`

Output format. Allowed values: `json`, `table`. Default: `json`.

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.


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
| [pfazure run archive](#pfazure-run-archive) | Archive a run. |
| [pfazure run restore](#pfazure-run-restore) | Restore a run. |
| [pfazure run update](#pfazure-run-update) | Update a run. |
| [pfazure run download](#pfazure-run-download) | Download a run. |

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
                   [--resume-from] # require promptflow>=1.8.0
                   [--set]
                   [--subscription]
                   [--resource-group]
                   [--workspace-name]
```

#### Parameters

`--file -f`

Local path to the YAML file containing the prompt flow run specification; can be overwritten by other parameters. Reference [here](https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json) for YAML schema.

`--flow`

The flow source to create the run. It could be:
- Local path to the flow directory.
  ```bash
  pfazure run create --flow <path-to-flow-directory> --data <path-to-data-file> --column-mapping <key-value-pair>
  ```
- The flow name on azure with a prefix `azureml:`. Flow name is a guid that can be found from 2 ways:
  - After creating a flow to azure, it can be found in the printed message in "name" attribute.
  - Open a flow in azure portal, the guid is in the url. e.g. https://ml.azure.com/prompts/flow/{workspace-id}/{flow-name}/xxx
  ```bash
  pfazure run create --flow azureml:<flow-name> --data <path-to-data-file> --column-mapping <key-value-pair>
  ```

`--data`

Local path to the data file or remote data. e.g. azureml:name:version.

`--column-mapping`

Inputs column mapping, use `${data.xx}` to refer to data columns, use `${run.inputs.xx}` to refer to referenced run's data columns, and `${run.outputs.xx}` to refer to run outputs columns.

`--run`

Referenced flow run name. For example, you can run an evaluation flow against an existing run. For example, "pfazure run create --flow evaluation_flow_dir --run existing_bulk_run --column-mapping url='${data.url}'".

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

`--resume-from`

Create a run resume from an existing run. (Require promptflow>=1.8.0)
Example: `--resume-from <run_name>`

`--set`

Update an object by specifying a property path and value to set.
Example: `--set property1.property2=<value>`.

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

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

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

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

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

### pfazure run stream

Stream run logs to the console.

```bash
pfazure run stream --name
                   [--timeout]
                   [--subscription]
                   [--resource-group]
                   [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--timeout`

Timeout in seconds. If the run stays in the same status and produce no new logs in a period longer than the timeout value, the stream operation will abort. Default value is 600 seconds

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

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

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

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

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

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

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.

### pfazure run archive

Archive a run.

```bash
pfazure run archive --name
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.


### pfazure run restore

Restore a run.

```bash
pfazure run restore --name
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Parameters

`--name -n`

Name of the run.

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.


### pfazure run update

Update a run's metadata, such as `display name`, `description` and `tags`.

```bash
pfazure run update --name
                    [--set display_name="<value>" description="<value>" tags.key="<value>"]
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Examples

Set `display name`, `description` and `tags`:

```bash
pfazure run update --name <run_name> --set display_name="<value>" description="<value>" tags.key="<value>"
```


#### Parameters

`--name -n`

Name of the run.

`--set`

Set meta information of the run, like `display_name`, `description` or `tags`. Example: --set <key>=<value>.

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.


### pfazure run download

Download a run's metadata, such as `input`, `output`, `snapshot` and `artifact`. After the download is finished,  you can use `pf run create --source <run-info-local-folder>` to register this run as a local run record, then you can use commands like `pf run show/visualize` to inspect the run just like a run that was created from local flow.

```bash
pfazure run download --name
                    [--output]
                    [--overwrite]
                    [--subscription]
                    [--resource-group]
                    [--workspace-name]
```

#### Examples

Download a run data to local:
```bash
pfazure run download --name <name> --output <output-folder-path>
```

#### Parameters

`--name -n`

Name of the run.

`--output -o`

Output folder path to store the downloaded run data. Default to be `~/.promptflow/.runs` if not specified

`--overwrite`

Overwrite the existing run data if the output folder already exists. Default to be `False` if not specified

`--subscription`

Subscription id, required when there is no default value from `az configure`.

`--resource-group -g`

Resource group name, required when there is no default value from `az configure`.

`--workspace-name -w`

Workspace name, required when there is no default value from `az configure`.
