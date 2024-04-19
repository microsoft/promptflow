# promptflow-devkit package

## v1.10.0 (Upcoming)

### Features Added
- Flow supports file as inputs of flow tests, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#pf-flow-test) for more details.

## 1.9.0 (2024.04.17)

### Features Added
- Added autocomplete feature for linux, reach [here](https://microsoft.github.io/promptflow/reference/pf-command-reference.html#autocomplete) for more details.
- Support trace experience in flow test and batch run. See [here](https://microsoft.github.io/promptflow/how-to-guides/tracing/index.html) for more details.

### Improvements

- Improve pf cli command help message.

### Bugs Fixed
- Fix run name missing directory name in some scenario of `pf.run`.
- Raise not supported instead of 404 when trying to create Azure AI connection.
