# Prompt flow
![banner](examples/tutorials/quick-start/media/banner.png)

[![Python package](https://img.shields.io/pypi/v/promptflow)](https://pypi.org/project/promptflow/)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)

<h2>Facilitate high quality LLM-native apps to production</h2>

> Welcome to join us to make Prompt flow!

[Documentacion](https://expert-adventure-197jp7v.pages.github.io/) • [Quick Start](https://github.com/microsoft/promptflow/blob/main/docs/how-to-guides/quick-start.md)  • [Discord](https://discord.gg/bnXr6kxs) •  [Discussions](https://github.com/microsoft/promptflow/discussions) • [Issues](https://github.com/microsoft/promptflow/issues/new/choose) • [Contribute PRs](https://github.com/microsoft/promptflow/pulls).

**Prompt flow** is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality.

With prompt flow, you will be able to:

- **LLM-native apps power workflow**
    - Create executable workflows that link LLMs, prompts, Python code and other tools together.
    - Debug and iterate your flows, especially the interaction with LLMs with ease.
- **Facilitate high quality in development cycle**
    - Evaluate your flow's quality and performance with larger datasets.
    - Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
    - Deploy your flow to the serving platform you choose or integrate into your app's code base easily.
- **Enterprise security and scalability**
    - (Optional but highly recommended) Collaborate with your team by leveraging the cloud version of [Prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

------

## Get Started with Prompt flow ⚡

### ①- Installation

A python environment, `python=3.9` is recommended.

```sh
pip install promptflow promptflow-tools
```

(Optional) Install <img src="examples/tutorials/quick-start/media/logo_pf.png" alt="alt text" width="25"/><font color="darkblue"><b>Prompt flow VS Code extension</b></font>  - Flow Designer

Prompt flow provides an extension in VS Code for visualizing and editing your flows. You can search for it in the VS Code extension marketplace to install it.

### ② - Create the connection to store your OpenAI API key

Prompt flow offers a **safe** way to manage credentials or secrets for LLM APIs, that is **Connection**!

We need a connection yaml file connection.yaml:
  
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
name: open_ai_connection
type: open_ai
api_key: <test_key>
```

Then we can use CLI command to create the connection.

```sh
pf connection create -f connection.yaml
```

### ③ - Initialize a prompt flow from template

Prompt flow currently supports three types of flow templates: `standard` (default), `chat`(suitable for chat scenarios) and `evaluation`(suitable for evaluation purposes).

```sh
pf flow init --flow my_chatbot --type chat
```

This command will create a new **flow folder** named "my_chatbot" using the "chat" template.

> You can choose to directly run our sample flows. Click to start your [Get started with web classification flow](examples/flows/standard/web-classification/README.md) journey!

### ④ - Quick test your flow

Open the `flow.dag.yaml` file in the "my_chatbot" flow folder, specify the connection name you created in the previous step in the `connection` field, specify the model name in the `model` field, for example:

```yaml
  ......
  inputs:
    model: gpt-4
    temperature: 0
    top_p: 1
    max_tokens: 256
    presence_penalty: 0
    frequency_penalty: 0
    chat_history: ${inputs.chat_history}
    question: ${inputs.question}
    model: gpt-4
  connection: open_ai_connection
  provider: OpenAI
  ......
```

Now you want the flow to answer a math question correctly. Open the `chat.jinia2` file in the folder, replace the **system prompt** with the following prompt:

```jinja2
system:
You are a helpful assistant. Please output the result number only.
```

Run the following command to test your prompt:

```sh
# test with flow inputs
!pf flow test --flow my_chatbot --inputs question="Compute $\\dbinom{16}{5}$."
```

## 🏃‍♂️Facilitating High-Quality with Prompt Flow🏃‍♀️

LLMs are known for their random nature, resulting in unstable generated answers. Fine-tuning the prompt can further enhance the reliability of the generated outputs. To accurately assess the quality of fine-tuned, testing with a larger dataset and comparing generated outputs to the ground truth is essential.  the prompt can further enhance the reliability of the generated outputs.

<h4><font color="Darkblue"> Tunning </font> + <font color="brown"> Batch Testing</font> + <font color="purple">Evaluation</font> = <font color="green">High Quality</font></h4>

<div class="columns">
  <div class="column">
    With prompt flow, in 10 minutes, test various prompts on multi-row inputs and evaluate the accuracy of the generated outputs against the ground truth. Find the best prompt for target accuracy and token cost effortlessly!
  </div>
  <div class="column">
     <img src="examples/tutorials/quick-start/media/realcase.png" alt="alt text" style="width:100%;"/>
  </div>
</div>

👉[Try to test this quick start case!](examples/tutorials/quick-start/prompt_tunning_case.md)

## Development Guide

Develop your LLM apps with Prompt flow: please start with our [docs](https://microsoft.github.io/promptflow) & [examples](./examples/README.md):
- [First look at prompt flow](https://expert-adventure-197jp7v.pages.github.io/how-to-guides/quick-start.html)
- [E2E Tutorial: Chat with PDF](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md)

Contribute to Prompt flow: please start with our dev setup guide: [dev_setup.md](./docs/dev/dev_setup.md).

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
