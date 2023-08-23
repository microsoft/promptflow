---
myst:
  html_meta:
    "description lang=en": "Prompt flow Doc"
html_theme.sidebar_secondary.remove: true
---

# Prompt flow

[**Prompt flow**](https://github.com/microsoft/promptflow) is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality. 

With prompt flow, you will be able to: 

- Create executable workflows that link LLMs, prompts, Python code and other tools together. 
- Debug and iterate your flows, especially the interaction with LLMs with ease.
- Evaluate your flow's quality and performance with larger datasets.
- Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
- Deploy your flow to the serving platform you choose or integrate into your app's code base easily.
- (Optional but highly recommended) Collaborate with your team by leveraging the cloud version of [Prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

> Welcome to join us to make Prompt flow better by
> participating [discussions](https://github.com/microsoft/promptflow/discussions),
> opening [issues](https://github.com/microsoft/promptflow/issues/new/choose),
> submitting [PRs](https://github.com/microsoft/promptflow/pulls),
> and learn our recent [changes](./changelog/sdk-change-log.md).

This documentation site contains guides for prompt flow sdk, cli and vscode extension users.

```{gallery-grid}
:grid-columns: 1 2 2 2
- header: "🚀 Quick Start"
  content: "
    A quick guide of how to developing and running your first prompt flow.<br/><br/>
    - [Start your prompt flow journey](how-to-guides/quick-start.md)<br/>
    - [E2E development tutorial: chat with PDF](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md)<br/>
    - Learn more: [tutorials & samples](tutorials/index.md)<br/>
  "

- header: "📒 How-to Guides"
  content: "
    Articles guide different user roles to done a specific task in prompt flow.<br/><br/>
    - [Initialize and test a flow](how-to-guides/init-and-test-a-flow.md)<br/>
    - [Run and evaluate a flow](how-to-guides/run-and-evaluate-a-flow.md)<br/>
    - [Tune prompts using variants](how-to-guides/tune-prompts-with-variants.md)<br/>
    - [Deploy and export a flow](how-to-guides/deploy-and-export-a-flow.md)<br/>
  "
```

Reach more details about concepts and tools of prompt flow.
```{gallery-grid}
:grid-columns: 1 2 2 2
- header: "📑 Concepts"
  content: "
    Introduction of key concepts of the core features of prompt flow.<br/><br/>
    - [Flows](concepts/concept-flows.md)<br/>
    - [Tools](concepts/concept-tools.md)<br/>
    - [Connections](concepts/concept-connections.md)<br/>
  "


- header: "🔍 Reference"
  content: "
    Useful resources & reference link.<br/><br/>
    - Command line Interface reference: [pf](reference/pf-command-reference.md)<br/>
    - Tool reference: [LLM Tool](reference/tools-reference/llm-tool.md), [Python Tool](reference/tools-reference/python-tool.md), [Prompt Tool](reference/tools-reference/prompt-tool.md)<br/>
  "
```

```{toctree}
:hidden:
:maxdepth: 2
concepts/index
```

```{toctree}
:hidden:
:maxdepth: 1
how-to-guides/index
```

```{toctree}
:hidden:
:maxdepth: 1
tutorials/index
```

```{toctree}
:hidden:
:maxdepth: 1
reference/index
```

```{toctree}
:hidden:
:maxdepth: 1
cloud/index
```

```{toctree}
:hidden:
:maxdepth: 1
changelog/index
```