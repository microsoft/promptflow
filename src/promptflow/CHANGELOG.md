# Release History

## 0.1.0b8 (Upcoming)

### Features Added
- [Executor] Add average execution time and estimated execution time to batch run logs

### Bugs Fixed
- **pf config set**:
  - Fix bug for workspace `connection.provider=azureml` doesn't work as expected.
- [SDK/CLI] Fix the bug that using sdk/cli to submit batch run did not display the log correctly.
- [SDK/CLI] Fix encoding issues when input is non-English with `pf flow test`.
- [Executor] Fix the bug can't read file containing "Private Use" unicode character.
- [SDK/CLI] Fix string type data will be converted to integer/float.

### Improvements

- [SDK/CLI] Experience improvements in `pf run visualize` page:
  - Add column status.
  - Support opening flow file by clicking run id.


## 0.1.0b7.post1 (2023.09.28)

### Bug Fixed
- Fix extra dependency bug when importing `promptflow` without `azure-ai-ml` installed.

## 0.1.0b7 (2023.09.27)

### Features Added

- **pf flow validate**: support validate flow
- **pf config set**: support set user-level promptflow config.
  - Support workspace connection provider, usage: `pf config set connection.provider=azureml:/subscriptions/<subscription_id>/resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/workspaces/<workspace_name>`
- Support override openai connection's model when submitting a flow. For example: `pf run create --flow ./ --data ./data.jsonl --connection llm.model=xxx`

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

## 0.1.0b6 (2023.09.15)

### Features Added

- [promptflow][Feature] Store token metrics in run properties

### Bugs Fixed

- Refine error message body for flow_validator.py
- Refine error message body for run_tracker.py
- [Executor][Internal] Add some unit test to improve code coverage of log/metric
- [SDK/CLI] Update portal link to remove flight.
- [Executor][Internal] Improve inputs mapping's error message.
- [API] Resolve warnings/errors of sphinx build

## 0.1.0b5 (2023.09.08)

### Features Added

- **pf run visualize**: support lineage graph & display name in visualize page

### Bugs Fixed

- Add missing requirement `psutil` in `setup.py`

## 0.1.0b4 (2023.09.04)

### Features added

- Support `pf flow build` commands

## 0.1.0b3 (2023.08.30)

- Minor bug fixes.

## 0.1.0b2 (2023.08.29)

- First preview version with major CLI & SDK features.

### Features added

- **pf flow**: init/test/serve/export
- **pf run**: create/update/stream/list/show/show-details/show-metrics/visualize/archive/restore/export
- **pf connection**: create/update/show/list/delete
- Azure AI support:
    - **pfazure run**: create/list/stream/show/show-details/show-metrics/visualize


## 0.1.0b1 (2023.07.20)

- Stub version in Pypi.
