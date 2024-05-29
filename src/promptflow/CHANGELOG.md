# Release History
## v1.12.0 (Upcoming)

### Bugs fixed
- [promptflow-core] Fix ChatUI can't work in docker container when running image build with `pf flow build`.

## v1.12.0 (Upcoming)

### Improvements
- [promptflow-devkit] Add retry logic when uploading run details to cloud.

## v1.11.0 (2024.05.17)

### Announcement

- Introducing flex flow - design powerful LLM apps with the flexibility of Python functions or classes, and seamlessly test and run your logic with our VS Code Extension. Learn more about flex flow [here](https://microsoft.github.io/promptflow/how-to-guides/develop-a-flex-flow/index.html)
- Introducing prompty - an experimental feature by for streamlining the creation of prompt templates. Simplify your development with .prompty files and elevate your prompts with ease! Learn more about prompty [here](https://microsoft.github.io/promptflow/how-to-guides/develop-a-prompty/index.html).

### Features Added

- [promptflow-devkit]: Upload local run details to cloud when trace destination is configured to cloud. See [here](https://microsoft.github.io/promptflow/cloud/azureai/tracing/run_tracking.html) for more details.
- [promptflow-core]: Support modifying the promptflow logger format through environment variables, reach [here](https://microsoft.github.io/promptflow/how-to-guides/faq.html#set-logging-format) for more details.

### Improvements
- [promptflow-devkit]: Interactive browser credential is excluded by default when using Azure AI connections, user could set `PF_NO_INTERACTIVE_LOGIN=False` to enable it.
- [promptflow-devkit]: Add new `--engine` parameter for `pf flow serve`. This parameter can be used to switch python serving engine between `flask` and `fastapi`, currently it defaults to `flask`.
- [promptflow-azure]: Refine trace Cosmos DB setup process to print setup status during the process, and display error message from service when setup failed.
- [promptflow-devkit][promptflow-azure] - Return the secrets in the connection object by default to improve flex flow experience.
  - Reach the sub package docs for more details about this. [promptflow-devkit](https://microsoft.github.io/promptflow/reference/changelog/promptflow-devkit.html) [promptflow-azure](https://microsoft.github.io/promptflow/reference/changelog/promptflow-azure.html)
- [promptflow-azure] Check workspace/project trace Cosmos DB status and honor when create run in Azure.

### Bugs Fixed
- Fix the issue that import error will be raised after downgrading promptflow from >=1.10.0 to <1.8.0.
- Fix the issue that `pf flow serve` is broken with exception `NotADirectoryError`.
- [promptflow-devkit]: Fix the issue that chat window error is hard to understand.
- [promptflow-devkit]: Fix the perf issue because of dns delay when check pfs status.
- [promptflow-devkit]: Fix the issue that original flex yaml will be overridden when testing non-yaml flow
- [promptflow-devkit] Fix run snapshot does not honor gitignore/amlignore.

## v1.10.0 (2024.04.26)
### Features Added
- [promptflow-devkit]: Expose --ui to trigger a chat window, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#pf-flow-test) for more details.
- [promptflow-devkit]: Local serving container support using fastapi engine and tuning worker/thread num via environment variables, reach [here](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/deploy-using-docker.html) for more details.
- [promptflow-core]: Add fastapi serving engine support.
- [promptflow-devkit]: Support search experience with simple Python expression in trace UI, reach [here](https://microsoft.github.io/promptflow/how-to-guides/tracing/index.html) for more details.

## v1.9.0 (2024.04.17)

### Features Added
- [promptflow-devkit]: Added autocomplete feature for linux, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#autocomplete) for more details.
- [promptflow-devkit]: Support trace experience in flow test and batch run. See [here](https://microsoft.github.io/promptflow/how-to-guides/tracing/index.html) for more details.

### Bugs Fixed
- [promptflow-devkit] Fix run name missing directory name in some scenario of `pf.run`.
- [promptflow-devkit] Raise not supported instead of 404 when trying to create Azure AI connection.

### Others
- [promptflow-core] Connection default api version changed:
  - AzureOpenAIConnection: 2023-07-01-preview -> 2024-02-01
  - CognitiveSearchConnection: 2023-07-01-preview -> 2023-11-01


## v1.8.0 (2024.04.10)

### NOTICES
- `promptflow` package has been split into multiple packages. When installing `promptflow`, you will get the following packages:
  - `promptflow`:
    - `promptflow-tracing`: Tracing capability for promptflow.
    - `promptflow-core`: Core functionality to run flow.
    - `promptflow-devkit`: Development kit for promptflow.
    - `promptflow-azure`: Azure extra requires(`promptflow[azure]`) for promptflow to integrate with Azure.

### Features Added
- [SDK/CLI] Create a run with `resume_from`, note that only run created with `promptflow>=1.8.0` can be used as the value of `resume_from`:
  - CLI: Support `pf run create --resume-from <original-run-name>` to create a run resume from another run.
  - SDK: Support `pf.run(resume_from=<original-run-name>)` to create a run resume from another run.
- [SDK/CLI][azure] Create a run with `resume_from`.
  - CLI: Support `pfazure run create --resume-from <original-run-name>` to create a run resume from another run.
  - SDK: Support `p.run(resume_from=<original-run-name>)` to create a run resume from another run.

## v1.7.0 (2024.03.25)

### NOTICES
- Import warnings will be printed when importing from `promptflow` namespace, please use imports from new namespaces
  suggested in the warning message.

### Features Added
- [Batch] Added per-line logging for batch runs, stored under the `flow_logs` folder.
- [SDK/CLI] Support `AzureOpenAIConnection.from_env` and `OpenAIConnection.from_env`. Reach more details [here](https://microsoft.github.io/promptflow/how-to-guides/manage-connections.html#load-from-environment-variables).

### Bugs Fixed

- [SDK/CLI] environment variable `PF_HOME_DIRECTORY` doesn't work for run details & logs.
- [SDK/CLI] Support override hard coded "deployment_name" and "model".
- [SDK] `connection.provider` config doesn't work when calling flow as a function.
- [SDK/CLI] Support override unprovided connection inputs in nodes.

## v1.6.0 (2024.03.01)

### Features Added

- [CLI] Support configuring environment variable to directly use `AzureCliCredential` for `pfazure` commands.
  ```
  PF_USE_AZURE_CLI_CREDENTIAL=true
  ```
- [SDK/CLI] Support setting timeout for `pfazure run stream`.
- [SDK/CLI] Support `pfazure flow update` to update flow's metadata like `display_name`, `description` or `tags`.
- [SDK/CLI][azure] Support [identity support](https://microsoft.github.io/promptflow/reference/run-yaml-schema-reference.html#identity-schema) for run for automatic runtime.

### Bugs Fixed

- [SDK/CLI] Tool meta generated by script tool contains inputs setting.

### Improvements

- Bump `cryptography` lower bound to 42.0.4.
- [Executor] Modify the default worker count for batch run from 16 to 4.

### Bugs Fixed

- [SDK/CLI][azure] Fixed automatic runtime session id cache when image updated.

## v1.5.0 (2024.02.06)

### Features Added

- [SDK/CLI][azure] Support specify compute instance as session compute in run.yaml
- [SDK/CLI][azure] Stop support specifying `idle_time_before_shutdown_minutes` for automatic runtime since each session will be auto deleted after execution.

### Bugs Fixed

- [SDK/CLI] The inputs of node test allows the value of reference node output be passed directly in.
- [SDK/CLI][azure] Fixed bug for cloud batch run referencing registry flow with automatic runtime.
- [SDK/CLI] Fix "Without Import Data" in run visualize page when invalid JSON value exists in metrics.
- [SDK/CLI][azure] Fix azureml serving get UAI(user assigned identity) token failure bug.
- [SDK/CLI] Fix flow as function connection override when node has default variant.

### Improvements

- [SDK/CLI] For `pf run delete`, `pf connection delete`, introducing an option to skip confirmation prompts.
- [SDK/CLI] Move pfs extra dependency to required dependency.

## v1.4.0 (2024.01.22)

### Features Added

- [Executor] Calculate system_metrics recursively in api_calls.
- [Executor] Add flow root level api_calls, so that user can overview the aggregated metrics of a flow.
- [Executor] Add @trace decorator to make it possible to log traces for functions that are called by tools.
- [Tool] InputSetting of tool supports passing undefined configuration.
- [SDK/CLI][azure] Switch automatic runtime's session provision to system wait.
- [SDK/CLI] Add `--skip-open-browser` option to `pf flow serve` to skip opening browser.
- [SDK/CLI][azure] Support submit flow to sovereign cloud.
- [SDK/CLI] Support `pf run delete` to delete a run irreversibly.
- [SDK/CLI][azure] Automatically put requirements.txt to flow.dag.yaml if exists in flow snapshot.
- [SDK/CLI] Support `pf upgrade` to upgrade prompt flow to the latest version.
- [SDK/CLI] Support env variables in yaml file.

### Bugs Fixed

- Fix unaligned inputs & outputs or pandas exception during get details against run in Azure.
- Fix loose flow path validation for run schema.
- Fix "Without Import Data" in run visualize page results from invalid JSON value (`-Infinity`, `Infinity` and `NaN`).
- Fix "ValueError: invalid width -1" when show-details against long column(s) in narrow terminal window.
- Fix invalid tool code generated when initializing the script tool with icon.

### Improvements

- [SDK/CLI] For `pfazure flow create`:
  - If used by non-msft tenant user, use user name instead of user object id in the remote flow folder path. (e.g. `Users/<user-name>/promptflow`).
  - When flow has unknown attributes, log warning instead of raising error.
  - Use local flow folder name and timestamp as the azure flow file share folder name.
- [SDK/CLI] For `pf/pfazure run create`, when run has unknown attribute, log warning instead of raising error.
- Replace `pyyaml` with `ruamel.yaml` to adopt YAML 1.2 specification.

## v1.3.0 (2023.12.27)

### Features Added

- [SDK/CLI] Support `pfazure run cancel` to cancel a run on Azure AI.
- Add support to configure prompt flow home directory via environment variable `PF_HOME_DIRECTORY`.
  - Please set before importing `promptflow`, otherwise it won't take effect.
- [Executor] Handle KeyboardInterrupt in flow test so that the final state is Canceled.

### Bugs Fixed

- [SDK/CLI] Fix single node run doesn't work when consuming sub item of upstream node

### Improvements

- Change `ruamel.yaml` lower bound to 0.17.10.
- [SDK/CLI] Improve `pfazure run download` to handle large run data files.
- [Executor] Exit the process when all async tools are done or exceeded timeout after cancellation.

## v1.2.0 (2023.12.14)

### Features Added

- [SDK/CLI] Support `pfazure run download` to download run data from Azure AI.
- [SDK/CLI] Support `pf run create` to create a local run record from downloaded run data.

### Bugs Fixed

- [SDK/CLI] Removing telemetry warning when running commands.
- Empty node stdout & stderr to avoid large visualize HTML.
- Hide unnecessary fields in run list for better readability.
- Fix bug that ignores timeout lines in batch run status summary.

## v1.1.1 (2023.12.1)

### Bugs Fixed

- [SDK/CLI] Fix compatibility issue with `semantic-kernel==0.4.0.dev0` and `azure-ai-ml==1.12.0`.
- [SDK/CLI] Add back workspace information in CLI telemetry.
- [SDK/CLI] Disable the feature to customize user agent in CLI to avoid changes on operation context.
- Fix openai metrics calculator to adapt openai v1.

## v1.1.0 (2023.11.30)

### Features Added

- Add `pfazure flow show/list` to show or list flows from Azure AI.
- Display node status in run visualize page graph view.
- Add support for image input and output in prompt flow.
- [SDK/CLI] SDK/CLI will collect telemetry by default, user can use `pf config set telemetry.enabled=false` to opt out.
- Add `raise_on_error` for stream run API, by default we raise for failed run.
- Flow as function: consume a flow like a function with parameters mapped to flow inputs.
- Enable specifying the default output path for run.
  - Use `pf config set run.output_path=<output-path>` to specify, and the run output path will be `<output-path>/<run-name>`.
  - Introduce macro `${flow_directory}` for `run.output_path` in config, which will be replaced with corresponding flow directory.
  - The flow directory cannot be set as run output path, which means `pf config set run.output_path='${flow_directory}'` is invalid; but you can use child folder, e.g. `pf config set run.output_path='${flow_directory}/.runs'`.
- Support pfazure run create with remote flow.
  - For remote workspace flow: `pfazure run create --flow azureml:<flow-name>`
  - For remote registry flow: `pfazure run create --flow azureml://registries/<registry-name>/models/<flow-name>/versions/<flow-version>`
- Support set logging level via environment variable `PF_LOGGING_LEVEL`, valid values includes `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, default to `INFO`.
- Remove openai version restrictions

### Bugs Fixed

- [SDK/CLI] Fix node test with dict node input will raise "Required input(s) missing".
- [SDK/CLI] Will use run name as display name when display name not specified (used flow folder name before).
- [SDK/CLI] Fix pf flow build created unexpected layer of dist folder
- [SDK/CLI] Fix deploy prompt flow: connections value may be none

### Improvements

- Force 'az login' if using azureml connection provider in cli command.
- Add env variable 'PF_NO_INTERACTIVE_LOGIN' to disable interactive login if using azureml connection provider in promptflow sdk.
- Improved CLI invoke time.
- Bump `pydash` upper bound to 8.0.0.
- Bump `SQLAlchemy` upper bound to 3.0.0.
- Bump `flask` upper bound to 4.0.0, `flask-restx` upper bound to 2.0.0.
- Bump `ruamel.yaml` upper bound to 1.0.0.

## v1.0.0 (2023.11.09)

### Features Added

- [Executor] Add `enable_kwargs` tag in tools.json for customer python tool.
- [SDK/CLI] Support `pfazure flow create`. Create a flow on Azure AI from local flow folder.
- [SDK/CLI] Changed column mapping `${run.inputs.xx}`'s behavior, it will refer to run's data columns instead of run's inputs columns.

### Bugs Fixed

- [SDK/CLI] Keep original format in run output.jsonl.
- [Executor] Fix the bug that raise an error when an aggregation node references a bypassed node

### Improvements

- [Executor] Set the outputs of the bypassed nodes as None

## v0.1.0b8 (2023.10.26)

### Features Added

- [Executor] Add average execution time and estimated execution time to batch run logs
- [SDK/CLI] Support `pfazure run archive/restore/update`.
- [SDK/CLI] Support custom strong type connection.
- [SDK/CLI] Enable telemetry and won't collect by default, use `pf config set cli.telemetry_enabled=true` to opt in.
- [SDK/CLI] Exposed function `from promptflow import load_run` to load run object from local YAML file.
- [Executor] Support `ToolProvider` for script tools.

### Bugs Fixed

- **pf config set**:
  - Fix bug for workspace `connection.provider=azureml` doesn't work as expected.
- [SDK/CLI] Fix the bug that using sdk/cli to submit batch run did not display the log correctly.
- [SDK/CLI] Fix encoding issues when input is non-English with `pf flow test`.
- [Executor] Fix the bug can't read file containing "Private Use" unicode character.
- [SDK/CLI] Fix string type data will be converted to integer/float.
- [SDK/CLI] Remove the max rows limitation of loading data.
- [SDK/CLI] Fix the bug --set not taking effect when creating run from file.

### Improvements

- [SDK/CLI] Experience improvements in `pf run visualize` page:
  - Add column status.
  - Support opening flow file by clicking run id.

## v0.1.0b7.post1 (2023.09.28)

### Bug Fixed

- Fix extra dependency bug when importing `promptflow` without `azure-ai-ml` installed.

## v0.1.0b7 (2023.09.27)

### Features Added

- **pf flow validate**: support validate flow
- **pf config set**: support set user-level promptflow config.
  - Support workspace connection provider, usage: `pf config set connection.provider=azureml://subscriptions/<subscription_id>/resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/workspaces/<workspace_name>`
- Support override openai connection's model when submitting a flow. For example: `pf run create --flow ./ --data ./data.jsonl --connection llm.model=xxx --column-mapping url='${data.url}'`

### Bugs Fixed

- [Flow build] Fix flow build file name and environment variable name when connection name contains space.
- Reserve `.promptflow` folder when dump run snapshot.
- Read/write log file with encoding specified.
- Avoid inconsistent error message when executor exits abnormally.
- Align inputs & outputs row number in case partial completed run will break `pfazure run show-details`.
- Fix bug that failed to parse portal url for run data when the form is an asset id.
- Fix the issue of process hanging for a long time when running the batch run.

### Improvements

- [Executor][Internal] Improve error message with more details and actionable information.
- [SDK/CLI] `pf/pfazure run show-details`:
  - Add `--max-results` option to control the number of results to display.
  - Add `--all-results` option to display all results.
- Add validation for azure `PFClient` constructor in case wrong parameter is passed.

## v0.1.0b6 (2023.09.15)

### Features Added

- [promptflow][Feature] Store token metrics in run properties

### Bugs Fixed

- Refine error message body for flow_validator.py
- Refine error message body for run_tracker.py
- [Executor][Internal] Add some unit test to improve code coverage of log/metric
- [SDK/CLI] Update portal link to remove flight.
- [Executor][Internal] Improve inputs mapping's error message.
- [API] Resolve warnings/errors of sphinx build

## v0.1.0b5 (2023.09.08)

### Features Added

- **pf run visualize**: support lineage graph & display name in visualize page

### Bugs Fixed

- Add missing requirement `psutil` in `setup.py`

## v0.1.0b4 (2023.09.04)

### Features added

- Support `pf flow build` commands

## v0.1.0b3 (2023.08.30)

- Minor bug fixes.

## v0.1.0b2 (2023.08.29)

- First preview version with major CLI & SDK features.

### Features added

- **pf flow**: init/test/serve/export
- **pf run**: create/update/stream/list/show/show-details/show-metrics/visualize/archive/restore/export
- **pf connection**: create/update/show/list/delete
- Azure AI support:
  - **pfazure run**: create/list/stream/show/show-details/show-metrics/visualize

## v0.1.0b1 (2023.07.20)

- Stub version in Pypi.
