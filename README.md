# Prompt flow

[![banner](examples/tutorials/quick-start/media/PF_banner.png)](https://microsoft.github.io/promptflow)

[![Python package](https://img.shields.io/pypi/v/promptflow)](https://pypi.org/project/promptflow/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow)](https://pypi.org/project/promptflow/)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)
[![](https://dcbadge.vercel.app/api/server/bnXr6kxs?compact=true&style=flat)](https://discord.gg/bnXr6kxs)

> Welcome to join us to make Prompt flow!

[Documentacion](https://microsoft.github.io/promptflow) • [Quick Start](https://github.com/microsoft/promptflow/blob/main/docs/how-to-guides/quick-start.md)  • [Discord](https://discord.gg/bnXr6kxs) •  [Discussions](https://github.com/microsoft/promptflow/discussions) • [Issues](https://github.com/microsoft/promptflow/issues/new/choose) • [Contribute PRs](https://github.com/microsoft/promptflow/pulls).

**Prompt flow** is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality.

With prompt flow, you will be able to:

- **Create and Iteratively Develop Flow**
    - Create executable workflows that link LLMs, prompts, Python code and other tools together.
    - Debug and iterate your flows, especially the interaction with LLMs with ease.
- **Evaluate Flow Quality and Performance**
    - Evaluate your flow's quality and performance with larger datasets.
    - Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
    - Deploy your flow to the serving platform you choose or integrate into your app's code base easily.
- (Optional but highly recommended) Collaborate with your team by leveraging the cloud version of [Prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

### Concept Overview

![concept](examples/tutorials/quick-start/media/concept.png)
Learn more about the concept of Prompt flow [here](https://microsoft.github.io/promptflow/concepts/index.html).

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
> <summary>For Azure Open AI, follow the respective setup guide.</summary>
> 
> Create a new yaml file `azure_openai.yaml` with following template in the `my_chatbot` folder. Replace the `api_key` and `api_base` with your own Azure OpenAI API key and endpoint:
> 
> ```yaml
> $schema: https://azuremlschemas.azureedge.net/promptflow/latest/AzureOpenAIConnection.schema.json
> name: azure_open_ai_connection # name of the connection
> type: azure_open_ai  # Azure Open AI 
> api_key: "<aoai-api-key>" # replace with your Azure OpenAI API key
> api_base: "aoai-api-endpoint" # replace with your Azure OpenAI API endpoint
> api_type: "azure" 
> api_version: "2023-03-15-preview" # replace with your Azure OpenAI API version
> ```
> 
> Establish the connection by running:
> ```sh
> pf connection create --file ./my_chatbot/azure_openai.yaml
> ```
> </details>

For Open AI connection, directly establish the connection by running:


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

Interact with your chatbot via (Press `Ctrl + C` to end the session.):

```sh
pf flow test --flow ./my_chatbot --interactive
```

Congratulations! You have now prototyped your chatbot! 🎉 What's next?

<details>
<summary><b>Ensuring "High Quality” in production scenarios</b></summary>

LLMs' randomness can yield unstable answers. Fine-tuning prompts can improve output reliability.  For accurate quality assessment, it's essential to test with larger datasets and compare outcomes with the ground truth.

During fine-tuning the prompt, we also consider to strike a balance between the accuracy and the token cost of the LLM.

Invest just 15 minutes to understand how prompt flow accelerates prompt tuning, testing, and evaluation, to find an ideal prompt **(accuracy ↑,token ↓)**
<img src="examples/tutorials/quick-start/media/realcase.png" alt="comparison resutl" width=80%>
</details>

Try the [15-mins Easy Case](examples/tutorials/quick-start/promptflow-quality-improvement.md) on Tuning ➕ Batch Testing ➕ Evaluation ➡ Quality ready for production.

Next Step! Continue with the **Tutorial**  👇 section to delve deeper into Prompt flow.

## Tutorial 🏃‍♂️

Prompt Flow is a tool designed to **facilitate high quality LLM-native apps to production**, the development process in prompt flow follows these steps: develop a flow, improve the flow quality, deploy the flow to production.

### Develop your own LLM apps

[Getting Started with Prompt Flow](https://microsoft.github.io/promptflow/how-to-guides/quick-start.html): A step by step guidance to invoke your first flow run.

<details>
<summary><b>VS Code Extension</b> <img src="examples/tutorials/quick-start/media/logo_pf.png" alt="logo" width="20"/> -- a flow designer</summary>

We also offer a VS Code extension for an interactive flow development experience with UI. This is a detailed walkthrough step-by-step to create your own flow from scratch and invoke your first flow run.

[![vsc extension](https://img.youtube.com/vi/GmhasXd7sj4/0.jpg)](https://youtu.be/GmhasXd7sj4)

</details>

You can install it from the [visualstudio marketplace](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

### Learn from Use Cases

[Tutorial: Chat with PDF]((https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md)): An end-to-end tutorial on how to build a high quality chat application with prompt flow, including flow development and evaluation with metrics.
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
