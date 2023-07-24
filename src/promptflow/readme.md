# [Version Hash in origin Repo: daae003f011b71826b5a33d2c3aa8f7f3b8c8add]
## How to run the e2e test case

### Prepare secrets

There are two methods to prepare secrets:

#### Set by environment variable

For each secret name, set the following environment: `PROMPTFLOW_SECRETS.<secret_name>`
For example, `PROMPTFLOW_SECRETS.openai-api-key=xxx`

#### Set by config file

1. Run the command `cp connections.json.example connections.json`;
2. Put the values in the json file;
3. Set the environment `PROMPTFLOW_CONNECTIONS='connections.json'`;

### Test case

Please run the command `python tests/executor.py --batch_request tests/test_configs/executor_api_requests/batch_request_e2e.json`
For run mode tests, run commands

1. `python tests/executor.py --batch_request tests/test_configs/executor_api_requests/batch_request_e2e.json --run_mode SingleNode`
2. `python tests/executor.py --batch_request tests/test_configs/executor_api_requests/batch_request_e2e.json --run_mode FromNode`
3. (1) `python tests/test_configs/example_py/example_flow.py`

   (2)`python tests/executor.py --batch_request tests/test_configs/executor_api_requests/example_flow.json`
4. (1) `python tests/test_configs/example_py/qa_with_bing.py`

   (2)`python tests/executor.py --batch_request tests/test_configs/executor_api_requests/qa_with_bing.json`
