[![banner](../../examples/tutorials/quick-start/media/PF_banner.png)](https://microsoft.github.io/promptflow)

------

# Prompt flow

[![Python package](https://img.shields.io/pypi/v/promptflow)](https://pypi.org/project/promptflow/)
[![Python](https://img.shields.io/pypi/pyversions/promptflow.svg?maxAge=2592000)](https://pypi.python.org/pypi/promptflow/) 
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow)](https://pypi.org/project/promptflow/)
[![License: MIT](https://img.shields.io/github/license/microsoft/promptflow)](https://github.com/microsoft/promptflow/blob/main/LICENSE)
[![Discord](https://dcbadge.vercel.app/api/server/bnXr6kxs?compact=true&style=flat)](https://discord.gg/bnXr6kxs)
[![Doc](https://img.shields.io/badge/Doc-online-green)](https://microsoft.github.io/promptflow/index.html)
[![!Github](https://img.shields.io/github/stars/microsoft/promptflow?logo=github&color=pink&link=https%3A%2F%2Fgithub.com%2Fmicrosoft%2Fpromptflow)](https://github.com/microsoft/promptflow)


> Welcome to join us to make Prompt flow!

**Prompt flow** is a suite of development tools designed to streamline the end-to-end development cycle of LLM-based AI applications, from ideation, prototyping, testing, evaluation to production deployment and monitoring. It makes prompt engineering much easier and enables you to build LLM apps with production quality.

With prompt flow, you will be able to:

- **Create and Iteratively Develop Flow**
    - Create executable workflows that link LLMs, prompts, Python code and other tools together.
    - Debug and iterate your flows, especially the interaction with LLMs with ease.
- **Evaluate Flow Quality and Performance**
    - Evaluate your flow's quality and performance with larger datasets.
    - Integrate the testing and evaluation into your CI/CD system to ensure quality of your flow.
- **Streamlined Development Cycle for Production**
    - Deploy your flow to the serving platform you choose or integrate into your app's code base easily.
    - (Optional but highly recommended) Collaborate with your team by leveraging the cloud version of [Prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2).

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

![interactive](../../examples/tutorials/quick-start/media/interactive.gif)

#### Continue to delve deeper into [Prompt flow](https://github.com/microsoft/promptflow).
