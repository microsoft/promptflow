## Introduction

A flow utilizing the single sign on feature provided by [Unify](https://github.com/unifyai), as well as a basic chat tool compatible with the `unifyai` library. The tools package used for this flow extends the capabilities presented in the [unify-ai](.\unify-ai\README.md) flex-flow. 

For documentation of the library this tools package integrates into promptflow refer to [Unify AI documentation](https://unify.ai/docs).

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Tools Used in this Flow

- `chat_tool` tool from the `unify-integration` package.
- `single_sign_on` tool from the `unify-integration` package.
- `llm` tool from the `promptflow-tools` package.

## Getting Started

- Prepare your Unify AI account follow this [instruction](https://unify.ai/docs/index.html#getting-started) and get your `api_key` if you don't have one.
- Install the `Prompt flow` extension for `VS Code`.
- Open the flow [flow.dag.yaml](flow.dag.yaml), press the `Visual editor` button at the top of the flow file or use the key shortcut: `Crtl + k` followed by `v`.
- Fill in the `api key` field from the `Unify SSO` node with your Unify api key from the first step.
- Run the flow.
- You can try out different `<model>@<provider>` options with a single API key.

## Contact

| Package Name | Description | Owner | Support Contact |  
|-|-|-|-|
|unify-integration| Multi-endpoint connection with dynamic routing and custom routers. | Kacper Kożdoń, Kato Steven, Omkar Khade | k.kozdon@gmail.com