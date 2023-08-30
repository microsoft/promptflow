# Development Guide

## Prerequisites

```bash
pip install -r requirements.txt
pip install pytest pytest-mock
```

## Run tests locally

- Create connection config file by `cp connections.json.example connections.json`.
- Fill in fields manually in `connections.json`.
- `cd tests` and run `pytest -s -v` to run all tests.

## Run tests in CI

Use this [workflow](https://github.com/microsoft/promptflow/actions/workflows/tools_secret_upload.yml) to upload secrets in key vault. The secrets you uploaded would be used in [tools tests](https://github.com/microsoft/promptflow/actions/workflows/tools_tests.yml). Note that you only need to upload the SECRETS.
  > [!NOTE] After triggering the workflow, kindly request approval from Promptflow Support before proceeding further.
