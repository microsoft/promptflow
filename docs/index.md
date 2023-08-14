---
myst:
  html_meta:
    "description lang=en": "Prompt flow Doc"
html_theme.sidebar_secondary.remove: true
---

# Prompt flow Doc

Simple and short articles grouped by topics, each introduces a core feature of prompt flow and how you can use it to address your specific use cases.

```{gallery-grid}
:grid-columns: 1 2 2 2
- header: "🚀 Quick Start"
  content: "
    An overview and quick guide of how to developing and running your first prompt flow.<br/><br/>
    - [What is prompt flow](overview-what-is-prompt-flow.md)<br/>
    - [Start your prompt flow journey](quick-start.md)<br/>
  "

- header: "📒 How-to Guides"
  content: "
    Articles guide different user roles to done a specific task in prompt flow.<br/><br/>
    - [Develop a standard flow](how-to-guides/how-to-develop-a-standard-flow.md)<br/>
    - [Develop an evaluation flow](how-to-guides/how-to-develop-an-evaluation-flow.md)<br/>
    - [Develop a chat flow](how-to-guides/how-to-develop-a-chat-flow.md)<br/>
  "
```
Guides for prompt flow sdk, cli and vscode extension users.

```{gallery-grid}
:grid-columns: 1 2 2 2
- header: "📂 Local"
  content: "
    How to develop, run and deploy a flow from local with prompt flow community version.<br/><br/>
    - [Quick start](community/local/quick-start.md)<br/>
    - [Run and evaluate a flow](community/local/run-and-evaluate-a-flow.md)<br/>
    - [Deploy and export a flow](community/local/deploy-and-export-a-flow.md)<br/>
  "

- header: "☁️ Cloud"
  content: "
    Move a flow from local to cloud and leverage Azure Machine Learning features.<br/><br/>
    - [Local to cloud](community/cloud/local-to-cloud.md)<br/>
    - [Flow in pipeline](community/cloud/flow-in-pipeline.md)<br/>
    - [CLI reference: pfazure](community/cloud/cli-command-reference.md)<br/>
  "
```

Reach more details about concepts and tools of prompt flow.
```{gallery-grid}
:grid-columns: 1 2 2 2
- header: "📑 Concepts"
  content: "
    Introduction of key concepts of the core features of prompt flow.<br/><br/>
    - [Tools](concepts/concept-tools.md)<br/>
    - [Flows](concepts/concept-flows.md)<br/>
    - [Connections](concepts/concept-connections.md)<br/>
    - [Runtimes](concepts/concept-runtime.md)<br/>
  "


- header: "🔍 Tool Reference"
  content: "
    Useful resources & reference link of tools.<br/><br/>
    - [LLM Tool](tools-reference/llm-tool.md)<br/>
    - [Python Tool](tools-reference/python-tool.md)<br/>
    - [Prompt Tool](tools-reference/prompt-tool.md)<br/>

  "
```

```{toctree}
:hidden:
:maxdepth: 1
overview-what-is-prompt-flow
```

```{toctree}
:hidden:
:maxdepth: 1
quick-start
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
community/index
```

```{toctree}
:hidden:
:maxdepth: 1
tools-reference/index
```
