# Development Guide

## Prerequisites

```bash
pip install -r requirements.txt
pip install pytest pytest-mock
```

## Run tests

- Create connection config file by `cp connections.json.example connections.json`.
- Fill in fields manually in `connections.json`.
- `cd tests` and run `pytest -s -v` to run all tests.

## Run tests in CI

Use this [workflow](https://github.com/microsoft/promptflow/actions/workflows/tools_secret_upload.yml) to upload secrets in key vault. The secrets you uploaded would be used in [tools tests](https://github.com/microsoft/promptflow/actions/workflows/tools_tests.yml). Note that you only need to upload the SECRETS.
  > [!NOTE] After triggering the workflow, kindly request approval from Promptflow Support before proceeding further.

## PR checkin criteria
When you submit your pull request, ensure it has a specific title and includes a detailed PR description with necessary screenshots of the tool verification result. This can help simplify our review process.

Additionally, your PR should also meet the following criteria:

### Code quality
The code you submit in your pull request should adhere to the following guidelines:
- **Maintain clean code**: The code should be clean, easy to understand, and well-structured to promote readability and maintainability.

- **Comment on your code**: Use comments to explain the purpose of certain code segments, particularly complex or non-obvious ones. This assists other developers in understanding your work.

- **Correct typos and grammatical errors**: Ensure that the code and file names are free from spelling mistakes and grammatical errors. This enhances the overall presentation and clarity of your code.

- **Avoid hard-coded values**: It is best to avoid hard-coding values unless absolutely necessary. Instead, use variables, constants, or configuration files, which can be easily modified without changing the source code.

- **Prevent code duplication**: Modify the original code to be more general instead of duplicating it. Code duplication can lead to longer, more complex code that is harder to maintain.

- **Implement effective error handling**: Good error handling is critical for troubleshooting customer issues and analyzing key metrics. Follow the guidelines provided in the [Error Handling Guideline](https://msdata.visualstudio.com/Vienna/_git/PromptFlow?path=/docs/error_handling_guidance.md&_a=preview) and reference the [exception.py](https://github.com/microsoft/promptflow/blob/main/src/promptflow-tools/promptflow/tools/exception.py) file for examples.


### Test coverage
Test coverage is crucial for maintaining code quality. Please adhere to the following guidelines:

- **Comprehensive Testing**: Include unit tests and e2e tests for any new functionality introduced.

- **Exception Testing**: Make sure to incorporate unit tests for all exceptions. These tests should verify status codes, error messages, and other important values. For reference, you can check out test_exceptions.py.

- **VSCode Testing**: If you're adding a new built-in tool, make sure to test your tool within the VSCode environment prior to submitting your PR. For more guidance on this, refer to test_tool_in_vscode.md.


### Documentation
Ensure to include documentation for your new built-in tool, following the guidelines below:
- **Error-Free Content**: Rectify all typographical and grammatical errors in the documentation. This will ensure clarity and readability.

- **Code Alignment**: The documentation should accurately reflect the current state of your code. Ensure that all described functionalities and behaviors match with your implemented code.

- Comprehensive Coverage: The documentation should be exhaustive, covering all aspects of the tool including its purpose, functionalities, and usage.
Functional Links: Verify that all embedded links within the documentation are functioning properly, leading to the correct resources or references.

- Rectify all typos and grammatical errors in the documentation.
- Ensure the documentation aligns with the current state of your code.
- The documentation should be comprehensive, covering all aspects of the tool.
- Confirm that all links within the documentation are functioning properly.



