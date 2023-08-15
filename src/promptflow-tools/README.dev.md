# Development Guide for Promptflow builtin tools

## Prerequisites

```bash
pip install -r requirements.txt
pip install pytest pytest-mock
```

## Run tests locally

- Create connection config file by `cp connections.json.example connections.json`.
- Fill in the keys and secrets manually in `connections.json`.
- `cd tests` and run `pytest -s -v` to run all tests.

## Run tests in CI

Use this [workflow](https://github.com/microsoft/promptflow/actions/workflows/tools_secret_upload.yml) to upload secrets in key vault. The secrets you uploaded would be used in [Promptflow Tools Test CI](https://github.com/microsoft/promptflow/actions/workflows/tools_tests.yml). Note that you only need to upload the SECRETS.
  > [!NOTE] After triggering the flow, kindly request approval from Promptflow Support before proceeding further.
