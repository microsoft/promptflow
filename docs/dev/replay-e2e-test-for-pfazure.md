# Replay end-to-end test for pfazure

This document introduces replay test for those tests located in [end-to-end tests for pfazure](../../src/promptflow/tests/sdk_cli_azure_test/e2etests/).

## Why we need replay test

End-to-end tests for pfazure targets to test the behavior that Prompt Flow SDK/CLI interacts with service, this process can be time consuming, error prone, and require credentials (which is unavailable to pull request from forked repository); all of these go against our intention for a smooth develop experience.

Therefore, we introduce replay test, which leverage [VCR.py](https://pypi.org/project/vcrpy/) to record all required network traffic to local files and replay during tests. In this way, we avoid the need of credentials, speed up and stabilize the test process.

## 3 test modes

- `live`: tests run against real backend, which is the way traditional end-to-end test do.
- `record`: tests run against real backend, and network traffic will be sanitized (filter sensitive and unnecessary requests/responses) and recorded to local files (recordings).
- `replay`: there is no real network traffic between SDK/CLI and backend, tests run against local recordings.

## How to record a test

We are planning to build a workflow to automatically update recordings on behalf of you, but it's still work in progress. Before that, you need to manually record it(them) locally.

To record a test, all you need is specifying environment variable `PROMPT_FLOW_TEST_MODE` to `'record'`; if you have a `.env` file, we recommend to specify it there. Then, just run the test that you want to record. Once the test completed, there should be one new YAML file located in `src/promptflow/tests/test_configs/recordings/`, containing the network traffic of the test - Congratulations! You have just recorded a test!

## How to run test(s) in replay mode

Specify environment variable `PROMPT_FLOW_TEST_MODE` to `'replay'` and run the test(s).
