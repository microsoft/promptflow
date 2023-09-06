[![banner](examples/tutorials/quick-start/media/banner.png)](https://microsoft.github.io/promptflow/index.html)

------

# Prompt flow

[![Python package](https://img.shields.io/pypi/v/promptflow)](https://pypi.org/project/promptflow/)
[![CLI](https://img.shields.io/badge/CLI-reference-blue)](https://microsoft.github.io/promptflow/reference/pf-command-reference.html)
[![vsc extension](https://img.shields.io/visual-studio-marketplace/i/prompt-flow.prompt-flow?logo=Visual%20Studio&label=Extension%20install)](https://microsoft.github.io/promptflow/reference/pf-command-reference.html)
[![Doc](https://img.shields.io/badge/Doc-online-green)](https://microsoft.github.io/promptflow/index.html)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow)](https://pypi.org/project/promptflow/)
[![Issue](https://img.shields.io/github/issues/microsoft/promptflow)](https://github.com/microsoft/promptflow/issues/new/choose)
[![Discord](https://dcbadge.vercel.app/api/server/bnXr6kxs?compact=true&style=flat)](https://discord.gg/bnXr6kxs)
[![Discussions](https://img.shields.io/github/discussions/microsoft/promptflow)](https://github.com/microsoft/promptflow/issues/new/choose)
[![CONTRIBUTING](https://img.shields.io/badge/Contributing-8A2BE2)](https://github.com/microsoft/promptflow/blob/main/CONTRIBUTING.md)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)

> Welcome to join us to make Prompt flow!

**Prompt flow** is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality.

With prompt flow, you will be able to:

- **Create and Iteratively Develop [Flow](https://microsoft.github.io/promptflow/concepts/concept-flows.html)**
    - Create executable workflows that link LLMs, prompts, Python code and other tools together.
    - Debug and iterate your flows, especially the interaction with LLMs with ease.
- **Evaluate Flow Quality and Performance**
    - Evaluate your flow's quality and performance with larger datasets.
    - Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
- **Streamlined Development Cycle for Production**
    - Deploy your flow to the serving platform you choose or integrate into your app's code base easily.
    - (Optional but highly recommended) Collaborate with your team by leveraging the cloud version of [Prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

### Concept Overview

[![concept](examples/tutorials/quick-start/media/concept.png)](https://microsoft.github.io/promptflow/concepts/concept-connections.html)

------

## Installation

Ensure you have a python environment, `python=3.9` is recommended.

```sh
pip install promptflow promptflow-tools
```

## Quick Start ⚡

<details>
<summary><b>Create a chatbot with prompt flow</b></summary>
 It creates a new <b>flow folder</b> named my_chatbot and generates the necessary flow files within it. The --flow argument is the path to the flow folder.
</details>

Initiate a prompt flow from a chat template:

```sh
pf flow init --flow ./my_chatbot --type chat
```

<details>
<summary><b>Setup a connection for your API key</b></summary>
Navigate to the `my_chatbot` folder, you can find a yaml file named `openai.yaml` file, which is the definition of the connection to store your Open AI key.
</details>

> <details>
> <summary>For Azure OpenAI key, establish the connection by running:</summary>
>
> ```sh
> # Override keys and endpoint with --set to avoid yaml file changes
> pf connection create --file ./my_chatbot/azure_openai.yaml --set api_key=<your_api_key> api_base=<your_api_endpoint>
> ```
> </details>

For OpenAI key, establish the connection by running:


```sh
# Override keys with --set to avoid yaml file changes
pf connection create --file ./my_chatbot/openai.yaml --set api_key=<your_api_key>
```

<details>
<summary><b>Chat with your flow</b></summary>
In the `my_chatbot` folder, there's a `flow.dag.yaml` file that outlines the flow, including inputs/outputs, tools, nodes, etc. Note we're using the connection named `open_ai_connection` in the `chat` node.
</details>

> <details>
> <summary>For Azure Open AI users, modify this file accordingly.</summary>
> Replace the 'node:' section with following content and specify the 'deployment_name' to the model deployment you'd like to use.
>
> ```yaml
> nodes:
> - name: chat
>   type: llm
>   source:
>     type: code
>     path: chat.jinja2
>   inputs:
>     deployment_name: <your_azure_open_ai_deployment_name>
>     max_tokens: '256'
>     temperature: '0.7'
>     chat_history: ${inputs.chat_history}
>     question: ${inputs.question}
>   api: chat
>   connection: azure_open_ai_connection
> ```
>  </details>

For OpenAI users, interact with your chatbot by running: (press `Ctrl + C` to end the session)

```sh
pf flow test --flow ./my_chatbot --interactive
```

Then you will see the chatbot in action:
![interactive](examples/tutorials/quick-start/media/interactive.gif)

Next Step! Continue with the **Tutorial**  👇 section to delve deeper into Prompt flow.

## Tutorial 🏃‍♂️

Prompt Flow is a tool designed to **facilitate high quality LLM-native apps to production**, the development process in prompt flow follows these steps: develop a flow, improve the flow quality, deploy the flow to production.

### Develop your own LLM apps

[Getting Started with Prompt Flow](https://microsoft.github.io/promptflow/how-to-guides/quick-start.html): A step by step guidance to invoke your first flow run.

#### VS Code Extension<img src="examples/tutorials/quick-start/media/logo_pf.png" alt="logo" width="25"/> 

We also offer a VS Code extension (a flow designer) for an interactive flow development experience with UI. You can install it from the <a href="https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow" target="_blank">visualstudio marketplace</a>.

<a href="https://youtu.be/05Utfsm0ptc" title="vsc demo" target="_blank"><img src="https://res.cloudinary.com/marcomontalbano/image/upload/v1694011417/video_to_markdown/images/youtube--05Utfsm0ptc-c05b58ac6eb4c4700831b2b3070cd403.jpg" alt="vsc demo" /></a>

### Learn from Use Cases

[Tutorial: Chat with PDF](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md): An end-to-end tutorial on how to build a high quality chat application with prompt flow, including flow development and evaluation with metrics.
> More examples can be found [here](./examples/README.md). We welcome contributions of new use cases!

### Setup for Contributors

If you're interested in contributing, please start with our dev setup guide: [dev_setup.md](./docs/dev/dev_setup.md).

Next Step! Continue with the **Contributing**  👇 section to to contribute to Prompt flow.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

## Code of Conduct

This project has adopted the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the
[Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
or contact [opencode@microsoft.com](mailto:opencode@microsoft.com)
with any additional questions or comments.

## License

Copyright (c) Microsoft Corporation. All rights reserved.

Licensed under the [MIT](LICENSE) license.
