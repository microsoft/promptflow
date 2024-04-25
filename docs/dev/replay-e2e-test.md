# Replay end-to-end tests

* This document introduces replay tests for those located in [sdk_cli_azure_test](../../src/promptflow-azure/tests/sdk_cli_azure_test/e2etests/) and [sdk_cli_test](../../src/promptflow-devkit/tests/sdk_cli_test/e2etests/).
* The primary purpose of replay tests is to avoid the need for credentials, Azure workspaces, OpenAI tokens, and to directly test prompt flow behavior.
* Although there are different techniques behind recording/replaying, there are some common steps to run the tests in replay mode.
* The key handle of replay tests is the environment variable `PROMPT_FLOW_TEST_MODE`.

## How to run tests in replay mode

After cloning the full repo and setting up the proper test environment following [dev_setup.md](./dev_setup.md), run the following command in the root directory of the repo:

1. If you have changed/affected tests in __sdk_cli_test__ : Copy or rename the file [dev-connections.json.example](../../src/promptflow/dev-connections.json.example) to `connections.json` in the same folder.
   * There are some python package version requirements for running the replay/record tests. It needs pydantic >= 2.0.0.
2. In your Python environment, set the environment variable `PROMPT_FLOW_TEST_MODE` to `'replay'` and run the test(s).

These tests should work properly without any real connection settings.

## Test modes

There are 3 representative values of the environment variable `PROMPT_FLOW_TEST_MODE`
- `live`: Tests run against the real backend, which is the way traditional end-to-end tests do.
- `record`: Tests run against the real backend, and network traffic will be sanitized (filter sensitive and unnecessary requests/responses) and recorded to local files (recordings).
- `replay`: There is no real network traffic between SDK/CLI and the backend, tests run against local recordings.

## Supported modules
* [promptflow-devkit](../../src/promptflow-devkit)
* [promptflow-azure](../../src/promptflow-azure)

## Update test recordings

To record a test, don’t forget to clone the full repo and set up the proper test environment following [dev_setup.md](./dev_setup.md):
1. Ensure you have installed dev version of promptflow-recording package.
   * If it is not installed, run `pip install -e src/promptflow-recording` in the root directory of the repo.
2. Prepare some data.
   * If you have changed/affected tests in __sdk_cli_test__: Copy or rename the file [dev-connections.json.example](../../src/promptflow/dev-connections.json.example) to `connections.json` in the same folder.
   * If you have changed/affected tests in __sdk_cli_azure_test__: prepare your Azure ML workspace, make sure your Azure CLI logged in, and set the environment variable `PROMPT_FLOW_SUBSCRIPTION_ID`, `PROMPT_FLOW_RESOURCE_GROUP_NAME`, `PROMPT_FLOW_WORKSPACE_NAME` and `PROMPT_FLOW_RUNTIME_NAME` (if needed) pointing to your workspace.
3. Record the test.
   * Specify the environment variable `PROMPT_FLOW_TEST_MODE` to `'record'`. If you have a `.env` file, we recommend specifying it there. Here is an example [.env file](../../src/promptflow/.env.example). Then, just run the test that you want to record.
4. Once the test completed.
   * If you have changed/affected tests in __sdk_cli_azure_test__: There should be one new YAML file located in [Azure recording folder](../../src/promptflow-recording/recordings/azure/), containing the network traffic of the test.
   * If you have changed/affected tests in __sdk_cli_test__: There may be changes in the folder [Local recording folder](../../src/promptflow-recording/recordings/local/).  Don’t worry if there are no changes, because similar LLM calls may have been recorded before.

## Techniques behind replay test

### Sdk_cli_azure_test

End-to-end tests for pfazure aim to test the behavior of the PromptFlow SDK/CLI as it interacts with the service. This process can be time-consuming, error-prone, and require credentials (which are unavailable to pull requests from forked repositories); all of these go against our intention for a smooth development experience.

Therefore, we introduce replay tests, which leverage [VCR.py](https://pypi.org/project/vcrpy/) to record all required network traffic to local files and replay during tests. In this way, we avoid the need for credentials, speed up, and stabilize the test process.

### Sdk_cli_test

sdk_cli_test often doesn’t use a real backend. It will directly invokes LLM calls from localhost. Thus the key target of replay tests is to avoid the need for OpenAI tokens. If you have OpenAI / Azure OpenAI tokens yourself, you can try recording the tests. Record Storage will not record your own LLM connection, but only the inputs and outputs of the LLM calls.

There are also limitations. Currently, recorded calls are:
* AzureOpenAI calls
* OpenAI calls
* tool name "fetch_text_content_from_url" and tool name "my_python_tool"