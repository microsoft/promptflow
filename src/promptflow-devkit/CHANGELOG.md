# promptflow-devkit package

## v1.12.0 (Upcoming)

### Improvements
- Add retry logic when uploading run details to cloud.

## v1.11.0 (2024.05.17)

### Features Added
- Upload local run details to cloud when trace destination is configured to cloud. See [here](https://microsoft.github.io/promptflow/cloud/azureai/tracing/run_tracking.html) for more details.

### Improvements
- Interactive browser credential is excluded by default when using Azure AI connections, user could set `PF_NO_INTERACTIVE_LOGIN=False` to enable it.
- Visualize flex flow run(s) switches to trace UI page.
- Add new `--engine` parameter for `pf flow serve`. This parameter can be used to switch python serving engine between `flask` and `fastapi`, currently it defaults to `flask`.
- Return the secrets in the connection object by default to improve flex flow experience.
  - Behaviors not changed: 'pf connection' command will scrub secrets.
  - New behavior: connection object by `client.connection.get` will have real secrets. `print(connection_obj)` directly will scrub those secrets. `print(connection_obj.api_key)` or `print(connection_obj.secrets)` will print the REAL secrets.

### Bugs Fixed
- Fix the issue that import error will be raised after downgrading promptflow from >=1.10.0 to <1.8.0.
- Fix the issue that `pf flow serve` is broken with exception `NotADirectoryError`.
- Fix the issue that chat window error is hard to understand.
- Fix the perf issue because of dns delay when check pfs status.
- Fix the issue that original flex yaml will be overridden when testing non-yaml flow
- Fix "Failed to load trace ... is not valid JSON" when traces inputs/outputs have invalid JSON values like `-Infinity`, `Infinity` and `NaN`.
- [promptflow-devkit] Fix run snapshot does not honor gitignore/amlignore.

## v1.10.0 (2024.04.26)

### Features Added
- Expose --ui to trigger a chat window, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#pf-flow-test) for more details.
- The `pf config set <key=value>` support set the folder where the config is saved by `--path config_folder` parameter,
  and the config will take effect when **os.getcwd** is a subdirectory of the specified folder.
- Local serving container support using fastapi engine and tuning worker/thread num via environment variables, reach [here](https://microsoft.github.io/promptflow/how-to-guides/deploy-a-flow/deploy-using-docker.html) for more details.
- Prompty supports to flow test and batch run, reach [here](https://microsoft.github.io/promptflow/how-to-guides/develop-a-prompty/index.html#testing-prompty) for more details.


## v1.9.0 (2024.04.17)

### Features Added
- Added autocomplete feature for linux, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#autocomplete) for more details.
- Support trace experience in flow test and batch run. See [here](https://microsoft.github.io/promptflow/how-to-guides/tracing/index.html) for more details.

### Improvements

- Improve pf cli command help message.

### Bugs Fixed
- Fix run name missing directory name in some scenario of `pf.run`.
- Raise not supported instead of 404 when trying to create Azure AI connection.
