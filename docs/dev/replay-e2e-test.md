# Replay end-to-end tests

* This document introduces replay test for those tests located in [sdk_cli_azure_test](../../src/promptflow/tests/sdk_cli_azure_test/e2etests/) and [sdk_cli_test](../../src/promptflow/tests/sdk_cli_test/e2etests/).
* The key purpose of replay test is to avoid the need of credentials, azure workspaces, openai tokens and to test promptflow behavior directly.
* Even though there are different techniques behind the recording/replay8ing, there are some common steps to run the tests in replay mode.
* The key handle of replay test is environment variable `PROMPT_FLOW_TEST_MODE`.

## (1 step version) How to run test in replay mode.

After clone the full repo and setup proper test environment following [dev_setup.md](./dev_setup.md), run the following command in the root directory of the repo:

1. If you have changed/affected tests in __sdk_cli_test__ : Copy or rename file [dev-connections.json.example](../../src/promptflow/dev-connections.json.example) to `connections.json` in the same folder.
2. In your python environ environment variable `PROMPT_FLOW_TEST_MODE` to `'replay'` and run the test(s).

These tests should work properly without any real connection settings.

## 3 test modes

There are 3 representative value of environment variable `PROMPT_FLOW_TEST_MODE`
- `live`: tests run against real backend, which is the way traditional end-to-end test do.
- `record`: tests run against real backend, and network traffic will be sanitized (filter sensitive and unnecessary requests/responses) and recorded to local files (recordings).
- `replay`: there is no real network traffic between SDK/CLI and backend, tests run against local recordings.

## How to record a test

To record a test, don't forget to clone the full repo and setup proper test environment following [dev_setup.md](./dev_setup.md):
1. Prepare some data.
   * If you have changed/affected tests in __sdk_cli_test__: copy or rename file [dev-connections.json.example](../../src/promptflow/dev-connections.json.example) to `connections.json` in the same folder.
   * If you have changed/affected tests in __sdk_cli_azure_test__: prepare a config.json, point your `az`` to proper tenant, subscription, resource group and workspace.
2. Record the test, Specifying environment variable `PROMPT_FLOW_TEST_MODE` to `'record'`; if you have a `.env` file, we recommend to specify it there. Then, just run the test that you want to record.
3. Once the test completed,
   * If you have changed/affected tests in __sdk_cli_azure_test__: there should be one new YAML file located in `src/promptflow/tests/test_configs/recordings/`, containing the network traffic of the test
   * If you have changed/affected tests in __sdk_cli_test__: there may be changes in folder `src/promptflow/tests/test_configs/node_recordings/`. Don't worry if there is no changes, similar llm calls may have been recorded before.

## Techniques behind replay test

### sdk_cli_azure_test

End-to-end tests for pfazure targets to test the behavior that prompt flow SDK/CLI interacts with service, this process can be time consuming, error prone, and require credentials (which is unavailable to pull request from forked repository); all of these go against our intention for a smooth develop experience.

Therefore, we introduce replay test, which leverage [VCR.py](https://pypi.org/project/vcrpy/) to record all required network traffic to local files and replay during tests. In this way, we avoid the need of credentials, speed up and stabilize the test process.

### sdk_cli_test

sdk_cli_test often don't use real backend. It will directly invoke llm calls from localhost. Thus the key target of replay test is to avoid the need of openai tokens. If you have openai / azure openai tokens yourself,
You can try recording the tests. Record Storage will not record your own llm connection, but only the input and output of the llm calls.

There are also limitations. Currently recorded calls are:
* AzureOpenAI calls
* python tool with name "fetch_text_content_from_url": this is dependency call of web classification tests.
* python tool with name "my_python_tool": this is llm calls of custom connection python tests.