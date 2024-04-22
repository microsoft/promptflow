# Prompt flow devkit

[![Python package](https://img.shields.io/pypi/v/promptflow-devkit)](https://pypi.org/project/promptflow-devkit/)
[![Python](https://img.shields.io/pypi/pyversions/promptflow.svg?maxAge=2592000)](https://pypi.python.org/pypi/promptflow-devkit/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow-devkit)](https://pypi.org/project/promptflow-devkit/)
[![CLI](https://img.shields.io/badge/CLI-reference-blue)](https://microsoft.github.io/promptflow/reference/pf-command-reference.html)
[![SDK](https://img.shields.io/badge/SDK-reference-blue)](https://microsoft.github.io/promptflow/reference/python-library-reference/promptflow-devkit/promptflow.client.html)
[![vsc extension](https://img.shields.io/visual-studio-marketplace/i/prompt-flow.prompt-flow?logo=Visual%20Studio&label=Extension%20)](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow)

[![Doc](https://img.shields.io/badge/Doc-online-green)](https://microsoft.github.io/promptflow/index.html)
[![Issue](https://img.shields.io/github/issues/microsoft/promptflow)](https://github.com/microsoft/promptflow/issues/new/choose)
[![Discussions](https://img.shields.io/github/discussions/microsoft/promptflow)](https://github.com/microsoft/promptflow/issues/new/choose)
[![CONTRIBUTING](https://img.shields.io/badge/Contributing-8A2BE2)](https://github.com/microsoft/promptflow/blob/main/CONTRIBUTING.md)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)

> Welcome to join us to make prompt flow better by
> participating [discussions](https://github.com/microsoft/promptflow/discussions),
> opening [issues](https://github.com/microsoft/promptflow/issues/new/choose),
> submitting [PRs](https://github.com/microsoft/promptflow/pulls).

## Introduction

The `promptflow-devkit` is a subpackage of [`promptflow`](https://pypi.org/project/promptflow). It contains features like :

- **Create and iteratively develop flow**
    - Debug and iterate your flows, especially the [interaction with LLMs](https://microsoft.github.io/promptflow/concepts/concept-connections.html) with ease.
    - Provide Tracing collector and UI to help user achieve comprehensive observability of their LLM applications.
- **Evaluate flow quality and performance**
    - Evaluate your flow's quality and performance with larger datasets.
    - Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
- **Streamlined development cycle for production**
    - Deploy your flow to the serving platform you choose or integrate into your app's code base easily.


NOTE:
- For users seeking a **minimal** dependency to execute a flow in serving or cloud run scenarios, consider installing the `promptflow-core` package. This package equips you with the fundamental features necessary for executing a `flow` in prompt flow.
- For users need to leverage the cloud version of [prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2), please install the `promptflow-azure` package.

## ChangeLog

Reach the full change log [here](https://microsoft.github.io/promptflow/reference/changelog/promptflow-devkit.html).
