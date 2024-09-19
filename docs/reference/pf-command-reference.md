# pf

Manage prompt flow resources with the prompt flow CLI.

| Command                         | Description                    |
|---------------------------------|--------------------------------|
| [pf flow](#pf-flow)             | Manage flows.                  |
| [pf connection](#pf-connection) | Manage connections.            |
| [pf run](#pf-run)               | Manage runs.                   |
| [pf tool](#pf-tool)             | Init or list tools.            |
| [pf config](#pf-config)         | Manage config for current user. |
| [pf service](#pf-service)       | Manage prompt flow service. |
| [pf upgrade](#pf-upgrade)       | Upgrade prompt flow CLI.       |
| [pf trace](#pf-trace)           | Manage traces.                 |

## pf flow

Manage promptflow flow flows.

| Command | Description |
| --- | --- |
| [pf flow init](#pf-flow-init) | Initialize a prompt flow directory. |
| [pf flow test](#pf-flow-test) | Test the prompt flow or flow node. |
| [pf flow validate](#pf-flow-validate) | Validate a flow and generate `flow.tools.json` for it. |
| [pf flow build](#pf-flow-build) | Build a flow for further sharing or deployment. |
| [pf flow serve](#pf-flow-serve) | Serve a flow as an endpoint. |

### pf flow init

Initialize a prompt flow directory.

```bash
pf flow init [--flow]
             [--entry]
             [--function]
             [--prompt-template]
             [--type]
             [--yes]
```

#### Examples

Create a flow folder with code, prompts and YAML specification of the flow.

```bash
pf flow init --flow <path-to-flow-direcotry>
```

Create an evaluation prompt flow

```bash
pf flow init --flow <path-to-flow-direcotry> --type evaluation
```

Create a flow in existing folder

```bash
pf flow init --flow <path-to-existing-folder> --entry <entry.py> --function <function-name> --prompt-template <path-to-prompt-template.md>
```

#### Optional Parameters

`--flow`

The flow name to create.

`--entry`

The entry file name.

`--function`

The function name in entry file.

`--prompt-template`

The prompt template parameter and assignment.

`--type`

The initialized flow type.  
accepted value: standard, evaluation, chat

`--yes --assume-yes -y`

Automatic yes to all prompts; assume 'yes' as answer to all prompts and run non-interactively.

### pf flow test

Test the prompt flow or flow node.

```bash
pf flow test --flow
             [--inputs]
             [--node]
             [--variant]
             [--debug]
             [--interactive]
             [--verbose]
             [--ui]
             [--collection]
```

#### Examples

Test the flow.

```bash
pf flow test --flow <path-to-flow-directory>
```

Test the flow from `json` file.

```bash
pf flow test --flow <path-to-flow-directory> --inputs inputs.json
```

Test the flow with first line from `jsonl` file.

```bash
pf flow test --flow <path-to-flow-directory> --inputs inputs.jsonl
```

Test the flow with input values.

```bash
pf flow test --flow <path-to-flow-directory> --inputs data_key1=data_val1 data_key2=data_val2
```

Test the flow with specified variant node.

```bash
pf flow test --flow <path-to-flow-directory> --variant '${node_name.variant_name}'
```

Test the single node in the flow.

```bash
pf flow test --flow <path-to-flow-directory> --node <node_name>
```

Debug the single node in the flow.

```bash
pf flow test --flow <path-to-flow-directory> --node <node_name> --debug
```

Chat in the flow.

```bash
pf flow test --flow <path-to-flow-directory> --node <node_name> --interactive
```

Chat in the chat window.

```bash
pf flow test --flow <path-to-flow-directory> --ui
```

Test the flow while log traces to a specific collection.

```bash
pf flow test --flow <path-to-flow-directory> --collection <collection>
```

#### Required Parameter

`--flow`

The flow directory to test.

#### Optional Parameters

`--inputs`

Input data for the flow. Example: --inputs data1=data1_val data2=data2_val

`--node`

The node name in the flow need to be tested.

`--variant`

Node & variant name in format of ${node_name.variant_name}.

`--debug`

Debug the single node in the flow.

`--interactive`

Start a interactive chat session for chat flow.

`--verbose`

Displays the output for each step in the chat flow.

`--ui`

The flag to start an interactive chat experience in local chat window.

### pf flow validate

Validate the prompt flow and generate a `flow.tools.json` under `.promptflow`. This file is required when using flow as a component in a Azure ML pipeline.

```bash
pf flow validate --source
                 [--debug]
                 [--verbose]
```

#### Examples

Validate the flow.

```bash
pf flow validate --source <path-to-flow>
```

#### Required Parameter

`--source`

The flow source to validate.

### pf flow build

Build a flow for further sharing or deployment.

```bash
pf flow build --source
              --output
              --format
              [--variant]
              [--verbose]
              [--debug]
```

#### Examples

Build a flow as docker, which can be built into Docker image via `docker build`.

```bash
pf flow build --source <path-to-flow> --output <output-path> --format docker
```

Build a flow as docker with specific variant.

```bash
pf flow build --source <path-to-flow> --output <output-path> --format docker --variant '${node_name.variant_name}'
```

#### Required Parameter

`--source`

The flow or run source to be used.

`--output`

The folder to output built flow. Need to be empty or not existed.

`--format`

The format to build flow into

#### Optional Parameters

`--variant`

Node & variant name in format of ${node_name.variant_name}.

`--verbose`

Show more details for each step during build.

`--debug`

Show debug information during build.

### pf flow serve

Serving a flow as an endpoint.

```bash
pf flow serve --source
              [--port]
              [--host]
              [--environment-variables]
              [--verbose]
              [--debug]
              [--skip-open-browser]
              [--engine]
```

#### Examples

Serve flow as an endpoint.

```bash
pf flow serve --source <path-to-flow>
```

Serve flow as an endpoint with specific port and host.

```bash
pf flow serve --source <path-to-flow> --port <port> --host <host> --environment-variables key1="`${my_connection.api_key}`" key2="value2"
```

Serve flow as an endpoint with specific port, host, environment-variables and fastapi serving engine.

```bash
pf flow serve --source <path-to-flow> --port <port> --host <host> --environment-variables key1="`${my_connection.api_key}`" key2="value2" --engine fastapi
```

#### Required Parameter

`--source`

The flow or run source to be used.

#### Optional Parameters

`--port`

The port on which endpoint to run.

`--host`

The host of endpoint.

`--environment-variables`

Environment variables to set by specifying a property path and value. Example: --environment-variable key1="\`${my_connection.api_key}\`" key2="value2". The value reference to connection keys will be resolved to the actual value, and all environment variables specified will be set into `os.environ`.

`--verbose`

Show more details for each step during serve.

`--debug`

Show debug information during serve.

`--skip-open-browser`

Skip opening browser after serve. Store true parameter.

`--engine`

Switch python serving engine between `flask` amd `fastapi`, default to `flask`.

## pf connection

Manage prompt flow connections.

| Command | Description |
| --- | --- |
| [pf connection create](#pf-connection-create) | Create a connection. |
| [pf connection update](#pf-connection-update) | Update a connection. |
| [pf connection show](#pf-connection-show) | Show details of a connection. |
| [pf connection list](#pf-connection-list) | List all the connection. |
| [pf connection delete](#pf-connection-delete) | Delete a connection. |

### pf connection create

Create a connection.

```bash
pf connection create --file
                     [--name]
                     [--set]
```

#### Examples

Create a connection with YAML file.

```bash
pf connection create -f <yaml-filename>
```

Create a connection with YAML file with override.

```bash
pf connection create -f <yaml-filename> --set api_key="<api-key>"
```

Create a custom connection with .env file; note that overrides specified by `--set` will be ignored.

```bash
pf connection create -f .env --name <name>
```

#### Required Parameter

`--file -f`

Local path to the YAML file containing the prompt flow connection specification.

#### Optional Parameters

`--name -n`

Name of the connection.

`--set`

Update an object by specifying a property path and value to set. Example: --set property1.property2=.

### pf connection update

Update a connection.

```bash
pf connection update --name
                     [--set]
```

#### Example

Update a connection.

```bash
pf connection update -n <name> --set api_key="<api-key>"
```

#### Required Parameter

`--name -n`

Name of the connection.

#### Optional Parameter

`--set`

Update an object by specifying a property path and value to set. Example: --set property1.property2=.

### pf connection show

Show details of a connection.

```bash
pf connection show --name
```

#### Required Parameter

`--name -n`

Name of the connection.

### pf connection list

List all the connection.

```bash
pf connection list
```

### pf connection delete

Delete a connection.

```bash
pf connection delete --name
```

#### Required Parameter

`--name -n`

Name of the connection.

## pf run

Manage prompt flow runs.

| Command | Description |
| --- | --- |
| [pf run create](#pf-run-create) | Create a run. |
| [pf run update](#pf-run-update) | Update a run metadata, including display name, description and tags. |
| [pf run stream](#pf-run-stream) | Stream run logs to the console. |
| [pf run list](#pf-run-list) | List runs. |
| [pf run show](#pf-run-show) | Show details for a run. |
| [pf run show-details](#pf-run-show-details) | Preview a run's intput(s) and output(s). |
| [pf run show-metrics](#pf-run-show-metrics) | Print run metrics to the console. |
| [pf run visualize](#pf-run-visualize) | Visualize a run. |
| [pf run archive](#pf-run-archive) | Archive a run. |
| [pf run restore](#pf-run-restore) | Restore an archived run. |

### pf run create

Create a run.

```bash
pf run create [--file]
              [--flow]
              [--data]
              [--column-mapping]
              [--run]
              [--variant]
              [--stream]
              [--environment-variables]
              [--connections]
              [--set]
              [--source]
              [--resume-from] # require promptflow>=1.8.0, and original run created with promptflow>=1.8.0
```

#### Examples

Create a run with YAML file.

```bash
pf run create -f <yaml-filename>
```

Create a run with YAML file and replace another data in the YAML file.

```bash
pf run create -f <yaml-filename> --data <path-to-new-data-file-relative-to-yaml-file>
```

Create a run from flow directory and reference a run.

```bash
pf run create --flow <path-to-flow-directory> --data <path-to-data-file> --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run <run-name> --variant '${summarize_text_content.variant_0}' --stream
```

Create a run from an existing run record folder.

```bash
pf run create --source <path-to-run-folder>
```

Create a run by specifying the `resume_from`. (Require promptflow>=1.8.0, and original run created with promptflow>=1.8.0)

Succeeded line result of the original run will be reused, only remaining/failed lines will be run.

```bash
pf run create --resume-from <original-run-name>
```

```bash
pf run create --resume-from <original-run-name> --name <new-run-name> --set display_name='A new run' description='my run description' tags.Type=Test
```

#### Optional Parameters

`--file -f`

Local path to the YAML file containing the prompt flow run specification; can be overwritten by other parameters. Reference [here](https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json) for YAML schema.

`--flow`

Local path to the flow directory. If --file is provided, this path should be relative path to the file.

`--data`

Local path to the data file. If --file is provided, this path should be relative path to the file.

`--column-mapping`

Inputs column mapping, use `${data.xx}` to refer to data columns, use `${run.inputs.xx}` to refer to referenced run's data columns, and `${run.outputs.xx}` to refer to run outputs columns.

`--run`

Referenced flow run name. For example, you can run an evaluation flow against an existing run. For example, "pf run create --flow evaluation_flow_dir --run existing_bulk_run".

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

`--source`

Local path to the existing run record folder.

### pf run update

Update a run metadata, including display name, description and tags.

```bash
pf run update --name
              [--set]
```

#### Example

Update a run

```bash
pf run update -n <name> --set display_name="<display-name>" description="<description>" tags.key="value"
```

#### Required Parameter

`--name -n`

Name of the run.

#### Optional Parameter

`--set`

Update an object by specifying a property path and value to set. Example: --set property1.property2=.

### pf run stream

Stream run logs to the console.

```bash
pf run stream --name
```

#### Required Parameter

`--name -n`

Name of the run.

### pf run list

List runs.

```bash
pf run list [--all-results]
            [--archived-only]
            [--include-archived]
            [--max-results]
```

#### Optional Parameters

`--all-results`

Returns all results.  
default value: False

`--archived-only`

List archived runs only.  
default value: False

`--include-archived`

List archived runs and active runs.  
default value: False

`--max-results -r`

Max number of results to return. Default is 50.  
default value: 50

### pf run show

Show details for a run.

```bash
pf run show --name
```

#### Required Parameter

`--name -n`

Name of the run.

### pf run show-details

Preview a run's input(s) and output(s).

```bash
pf run show-details --name
```

#### Required Parameter

`--name -n`

Name of the run.

### pf run show-metrics

Print run metrics to the console.

```bash
pf run show-metrics --name
```

#### Required Parameter

`--name -n`

Name of the run.

### pf run visualize

Visualize a run in the browser.

```bash
pf run visualize --names
```

#### Required Parameter

`--names -n`

Name of the runs, comma separated.

### pf run archive

Archive a run.

```bash
pf run archive --name
```

#### Required Parameter

`--name -n`

Name of the run.

### pf run restore

Restore an archived run.

```bash
pf run restore --name
```

#### Required Parameter

`--name -n`

Name of the run.

## pf tool

Manage promptflow tools.

| Command | Description |
| --- | --- |
| [pf tool init](#pf-tool-init) | Initialize a tool directory. |
| [pf tool list](#pf-tool-list) | List all tools in the environment. |
| [pf tool validate](#pf-tool-validate) | Validate tools. |

### pf tool init

Initialize a tool directory.

```bash
pf tool init [--package]
             [--tool]
             [--set]
```

#### Examples

Creating a package tool from scratch.

```bash
pf tool init --package <package-name> --tool <tool-name>
```

Creating a package tool with extra info.

```bash
pf tool init --package <package-name> --tool <tool-name> --set icon=<icon-path> category=<tool-category> tags="{'<key>': '<value>'}"
```

Creating a package tool from scratch.

```bash
pf tool init --package <package-name> --tool <tool-name>
```

Creating a python tool from scratch.

```bash
pf tool init --tool <tool-name>
```

#### Optional Parameters

`--package`

The package name to create.

`--tool`

The tool name to create.

`--set`

Set extra information about the tool, like category, icon and tags. Example: --set <key>=<value>.

### pf tool list

List all tools in the environment.

```bash
pf tool list [--flow]
```

#### Examples

List all package tool in the environment.

```bash
pf tool list
```

List all package tool and code tool in the flow.

```bash
pf tool list --flow <path-to-flow-direcotry>
```

#### Optional Parameters

`--flow`

The flow directory.

### pf tool validate

Validate tool.

```bash
pf tool validate --source
```

#### Examples

Validate single function tool.

```bash
pf tool validate -–source <package-name>.<module-name>.<tool-function>
```

Validate all tool in a package tool.

```bash
pf tool validate -–source <package-name>
```

Validate tools in a python script.

```bash
pf tool validate --source <path-to-tool-script>
```

#### Required Parameter

`--source`

The tool source to be used.


## pf config

Manage config for current user.

| Command                           | Description                                |
|-----------------------------------|--------------------------------------------|
| [pf config set](#pf-config-set)   | Set prompt flow configs for current user.  |
| [pf config show](#pf-config-show) | Show prompt flow configs for current user. |

### pf config set

Set prompt flow configs for current user, configs will be stored at ~/.promptflow/pf.yaml.

```bash
pf config set
```

#### Examples

**Connection provider**

Set connection provider to Azure ML workspace or Azure AI project for current user.

```bash
pf config set connection.provider="azureml://subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.MachineLearningServices/workspaces/<workspace-or-project-name>"
```

**Tracing**

Set trace destination to Azure ML workspace or Azure AI project.

```bash
pf config set trace.destination="azureml://subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.MachineLearningServices/workspaces/<workspace-or-project-name>"
```

Only log traces to local.

```bash
pf config set trace.destination="local"
```

Disable tracing feature.

```bash
pf config set trace.destination="none"
```

### pf config show

Show prompt flow configs for current user.

```bash
pf config show
```

#### Examples

Show prompt flow for current user.

```bash
pf config show
```

## pf service

Manage prompt flow service.

| Command                                 | Description                                   |
|-----------------------------------------|-----------------------------------------------|
| [pf service start](#pf-service-start)   | Start prompt flow service.                    |
| [pf service stop](#pf-service-stop)     | Stop prompt flow service.                     |
| [pf service status](#pf-service-status) | Display the started prompt flow service info. |

### pf service start

Start the prompt flow service.

```bash
pf service start [--port]
                 [--force]
                 [--debug]
```

#### Examples
Prompt flow will try to start the service on the default port 23333. If the port is already taken, prompt flow will 
sequentially probe new ports, incrementing by one each time. Prompt flow retains the port number for future reference 
and will utilize it for subsequent service startups.

```bash
pf service start
```

Forcefully start the prompt flow service. If the port is already in use, the existing service will be terminated and 
restart a new service

```bash
pf service start --force
```

Start the prompt flow service with a specified port. If the port is already taken, prompt flow will raise an error 
unless forcefully start the service with the `--force` flag. Upon availability, prompt flow retains the port number for 
future reference and will utilize it for subsequent service startups.

```bash
pf service start --port 65553
```

Start prompt flow service in foreground, displaying debug level logs directly in the terminal.
```bash
pf service start --debug
```

#### Optional Parameters

`--port -p`

The designated port of the prompt flow service and port number will be remembered if port is available.

`--force`

Force restart the existing service if the port is used.

`--debug`

Start prompt flow service in foreground, displaying debug level logs directly in the terminal.



### pf service stop

Stop prompt flow service.

```bash
pf service stop [--debug]
```

#### Example

Stop prompt flow service.

```bash
pf service stop
```

#### Optional Parameter

`--debug`

The flag to turn on debug mode for cli.

### pf service status

Display the started prompt flow service info.

```bash
pf service status
```


## pf upgrade

Upgrade prompt flow CLI.

| Command                     | Description                 |
|-----------------------------|-----------------------------|
| [pf upgrade](#pf-upgrade)   | Upgrade prompt flow CLI.    |

### Examples

Upgrade prompt flow without prompt and run non-interactively.

```bash
pf upgrade --yes
```

## pf trace

Manage prompt flow traces.

| Command                             | Description   |
| ----------------------------------- | ------------- |
| [pf trace delete](#pf-trace-delete) | Delete traces |

### pf trace delete

Delete traces.

```bash
pf trace delete [--run]
                [--collection]
                [--started-before]  # should combine with `collection`
```

#### Examples

Delete traces comes from a specific run.

```bash
pf trace delete --run <run-name>
```

Delete traces in a specific collection.

```bash
pf trace delete --collection <collection>
```

Delete traces in a specific collection started before a specific time.

```bash
# `started-before` should be in ISO 8601 format
pf trace delete --collection <collection> --started-before '2024-03-19T15:17:23.807563'
```

## Autocomplete

To activate autocomplete features for the pf CLI you need to add the following snippet to your ~/.bashrc or ~/.zshrc:

```bash
source <promptflow_package_install_root>/pf.completion.sh
```
