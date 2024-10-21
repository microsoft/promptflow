
# Unify Integration for Prompt Flow

## Introduction
This tool package provides access to [numerous endpoints](https://console.unify.ai/dashboard) and custom routers, with the option to employ dynamic routing to obtain responses from the best-suited model@provider for your task.

## Requirements
PyPI package: [`unify-integration`](https://pypi.org/project/unify-integration/).

- For local users:
    ```bash
    pip install unify-integration
    ```
    Recommended to be used with the [VS Code extension for Prompt flow](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

## Unify-specific inputs (optional)

| Name                | Type             | Description                                                                 | Required |
| ------------------- | ---------------- | --------------------------------------------------------------------------- | -------- |
| cost                | string           | Cost-per-token for the endpoint.                                             | No       |
| quality             | string           | The quality value of the model based on [dataset evaluations](https://console.unify.ai/dashboard) done by the oracle model. | No       |
| inter_token_latency | string           | The delay before a new token is output.                                      | No       |
| time_to_first_token | string           | The delay before the first token is generated                                | No       |
| connection          | CustomConnection | UnifyConnection using the [Unify client](https://github.com/unifyai/unify?tab=readme-ov-file#chatbot-agent) | No       |

---

## Overview

This repository provides an integration between Unify and Promptflow, allowing seamless optimization of large language models (LLMs) using Unify's capabilities. With this integration, users can dynamically select the optimal model based on quality, cost, and latency constraints, as well as benchmark models for specific tasks.

## Project Structure

```bash
.
├── dist/                          # Distribution files for installation
│   ├── unify_integration-0.0.14-py3-none-any.whl
│   └── unify_integration-0.0.14.tar.gz
├── tests/                         # Test files for the Unify integration
│   ├── __init__.py
│   ├── quick_test.py              # Quick tests for package tools
│   ├── test_unify_llm_tool.py     # Unit tests for Unify LLM tool functionality
│   └── test_unify_llm.py          # Additional unit tests for Unify LLM
├── unify_llm_tool/                # Unify tool package and connection settings
│   ├── __init__.py
│   ├── connections/
│   │   └── unify_connection.yml   # Configuration for the Unify connection
│   └── examples/                  # Example workflows for Unify integration
├── tools/                         # Tools available in the Unify integration
│   ├── yamls/
│   │   ├── benchmark_llm_tool.yaml # YAML for the benchmark LLM tool
│   │   ├── chat_tool.yaml          # YAML for the chat tool
│   │   ├── optimize_llm_tool.yaml  # YAML for the LLM optimization tool
│   │   └── single_sign_on_tool.yaml # YAML for Single Sign-On tool
├── .gitignore                     # Git ignore file
├── .pre-commit-config.yaml        # Pre-commit hooks configuration
├── generate_icon_data_uri.py      # Script to generate base64 icons for the project
├── LICENSE                        # License file
├── MANIFEST.in                    # Manifest for including package data
├── README.md                      # Project README file
├── requirements.txt               # Required dependencies
├── setup.cfg                      # Configuration for flake8, isort, etc.
├── setup.py                       # Setup script for the project
└── unify_icon.png                 # Icon for the project
```

## Installation

To install the project, you can either download the wheel or install the `unify_integration` package via pip:

```bash
pip install unify_integration-0.0.14-py3-none-any.whl
```

Alternatively, install directly from PyPI:

```bash
pip install unify-integration
```

## Tools and Features

### 1. **Optimize LLM Tool**
Optimize LLM selection based on task constraints like quality, cost, and time. The YAML file configuration allows customization of these parameters.

```yaml
unify_llm_tool.tools.optimize_llm_tool.optimize_llm:
  function: optimize_llm
  inputs:
    unify_api_key: '{{env: UNIFY_API_KEY}}'
    quality: "1"
    cost: "4.65e-03"
    time_to_first_token: "2.08e-05"
```

### 2. **Benchmark LLM Tool**
Benchmark multiple LLMs against a set of inputs to determine the best-performing model for a given task.

### 3. **Chat Tool**
Allows you to interact with custom endpoints using predefined or dynamic prompts.

### 4. **Single Sign-On Tool**
Single sign-on integration with multiple endpoints, streamlining the authentication process for various services.

## Testing

The `tests/` directory contains unit tests for each tool. You can run the tests using:

```bash
pytest tests/
```

