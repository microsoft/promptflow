# Prompt flow
![banner](examples/tutorials/quick-start/media/banner.png)

[![Python package](https://img.shields.io/pypi/v/promptflow)](https://pypi.org/project/promptflow/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow)](https://pypi.org/project/promptflow/)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)

<h2>Facilitate high quality LLM-native apps to production</h2>

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

## Get Started with Prompt flow ⚡

### ① - Installation

> [!Important] 
> A python environment, `python=3.9` is recommended.

```sh
pip install promptflow promptflow-tools
```

(Optional) Install <img src="examples/tutorials/quick-start/media/logo_pf.png" alt="alt text" width="25"/><font color="darkblue"><b>Prompt flow VS Code extension</b></font>  - Flow Designer

Prompt flow provides an extension in VS Code for visualizing and editing your flows. You can install it from [visualstudio marketplace](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

### ② - Create the connection to store your OpenAI API key

Create a folder for this quick start testing:

```sh
mkdir pf-test
```
```sh
cd pf-test
```

Create a yaml file `connection.yaml` in `pf-test` folder to define the connection:
  
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
name: open_ai_connection
type: open_ai
api_key: <test_key>
```

Run the following CLI command to create the connection:

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

Let your chatbot complete a specific task of solving a math problem, you need to inform the LLM about the task and target in your prompt.

Open the `chat.jinia2` file in the folder, overwrite the file content with the following prompt (tasks and targets are highlighted in the system prompt):

```jinja2
system:
You are an assistant specialized in math computation. Your task is to solve math problems. Please provide the result number only in your response. 

{% for item in chat_history %}
user:
{{item.inputs.question}}
assistant:
{{item.outputs.answer}}
{% endfor %}

user:
{{question}}
```

Run the following command to test your prompt on a single input question:

```sh
pf flow test --flow my_chatbot --interactive
```

Input the math question in the `User` section, for example, "James has 7 apples. 4 of them are red, and 3 of them are green. If he chooses 2 apples at random, what is the probability that both the apples he chooses are green?"

Click `Ctrl + C` to end the interactive testing.

## Prompt Flow value: Improve Quality 🏃‍♂️

LLMs are known for their random nature, resulting in unstable generated answers. Fine-tuning the prompt can further enhance the reliability of the generated outputs. To accurately assess the quality of fine-tuned, testing with a larger dataset and comparing generated outputs to the ground truth is essential.  the prompt can further enhance the reliability of the generated outputs.

<h3> Prototype ▶ Tunning  ➕  Batch Testing ➕ Evaluation ▶ Facilitate high quality LLM-native apps to production</h3>
 
| With prompt flow, in 10 minutes, test various prompts on multi-row inputs, evaluate accuracy against ground truth, and find the best prompt for target accuracy and token cost!| <img src="examples/tutorials/quick-start/media/realcase.png" alt="alt text" width="2000px"/>|  
| :------ | :------: |

👉[Try to tune the prompt, test and evaluate it!](examples/tutorials/quick-start/tune-your-prompt.md)

## Tutorial

Develop your LLM apps with Prompt flow: please start with our [docs](https://microsoft.github.io/promptflow) & [examples](./examples/README.md):
- [Getting Started with Prompt Flow](https://microsoft.github.io/promptflow/how-to-guides/quick-start.html): A step by step guidance to invoke your first flow run.
- [Tutorial: Chat with PDF](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md): An end-to-end tutorial on how to build a high quality chat application with prompt flow, including flow development and evaluation with metrics.

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
