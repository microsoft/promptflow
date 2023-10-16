# Chat flow
Chat flow is designed for conversational application development, building upon the capabilities of standard flow and providing enhanced support for chat inputs/outputs and chat history management. With chat flow, you can easily create a chatbot that handles chat input and output.

## Create connection for LLM tool to use
You can follow these steps to create a connection required by a LLM tool.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
# Create open ai connection
pf connection create --file openai.yaml --set api_key=<your_api_key> --name open_ai_connection

# Create azure open ai connection
# pf connection create --file azure_openai.yaml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Note in [flow.dag.yaml](flow.dag.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```
Please refer to connections [document](https://promptflow.azurewebsites.net/community/local/manage-connections.html) and [example](https://github.com/microsoft/promptflow/tree/main/examples/connections) for more details.

## Develop a chat flow

The most important elements that differentiate a chat flow from a standard flow are **Chat Input**, **Chat History**, and **Chat Output**.

- **Chat Input**: Chat input refers to the messages or queries submitted by users to the chatbot. Effectively handling chat input is crucial for a successful conversation, as it involves understanding user intentions, extracting relevant information, and triggering appropriate responses.

- **Chat History**: Chat history is the record of all interactions between the user and the chatbot, including both user inputs and AI-generated outputs. Maintaining chat history is essential for keeping track of the conversation context and ensuring the AI can generate contextually relevant responses. Chat History is a special type of chat flow input, that stores chat messages in a structured format.

- **Chat Output**: Chat output refers to the AI-generated messages that are sent to the user in response to their inputs. Generating contextually appropriate and engaging chat outputs is vital for a positive user experience.

A chat flow can have multiple inputs, but Chat History and Chat Input are required inputs in chat flow.

## Interact with chat flow

Promptflow CLI provides a way to start an interactive chat session for chat flow. Customer can use below command to start an interactive chat session:

```
pf flow test --flow <flow_folder> --interactive
```

After executing this command, customer can interact with the chat flow in the terminal. Customer can press **Enter** to send the message to chat flow. And customer can quit with **ctrl+C**.
Promptflow CLI will distinguish the output of different roles by color, <span style="color:Green">User input</span>, <span style="color:Gold">Bot output</span>, <span style="color:Blue">Flow script output</span>, <span style="color:Cyan">Node output</span>.

> =========================================<br>
> Welcome to chat flow, <You-flow-name>.<br>
> Press Enter to send your message.<br>
> You can quit with ctrl+C.<br>
> =========================================<br>
> <span style="color:Green">User:</span> What types of container software there are<br>
> <span style="color:Gold">Bot:</span> There are several types of container software available, including:<br>
> 1. Docker: This is one of the most popular containerization software that allows developers to package their applications into containers and deploy them across different environments.<br>
> 2. Kubernetes: This is an open-source container orchestration platform that automates the deployment, scaling, and management of containerized applications.<br>
>
> <span style="color:Green">User:</span> What's the different between them<br>
> <span style="color:Gold">Bot:</span> The main difference between the various container software systems is their functionality and purpose. Here are some key differences between them:<br>
> 1. Docker is more focused on container packaging and deployment, while Kubernetes is more focused on container orchestration and management.<br>
> 2. Kubernetes: Kubernetes is a container orchestration tool that helps manage and deploy containers at scale. It automates the deployment, scaling, and management of containerized applications across multiple hosts.<br>

If customer adds "--verbose" in the pf command, the output of each step will be displayed.

> =========================================<br>
> Welcome to chat flow, Template Chat Flow.<br>
> Press Enter to send your message.<br>
> You can quit with ctrl+C.<br>
> =========================================<br>
> <span style="color:Green">User:</span> What types of container software there are<br>
> <span style="color:Cyan">chat:</span> There are several types of container software available, including:<br>
> 1. Docker: A popular container platform that is widely used in the industry.<br>
> 2. Kubernetes: A container orchestration tool that helps manage and deploy containers at scale.<br>
>
> <span style="color:Gold">Bot:</span> There are several types of container software available, including:<br>
> 1. Docker: A popular container platform that is widely used in the industry.<br>
> 2. Kubernetes: A container orchestration tool that helps manage and deploy containers at scale.<br>
>
> <span style="color:Green">User:</span> What's the different between them<br>
> <span style="color:Cyan">chat:</span> The main differences between container software are in their architecture, feature sets, and use cases. Here are some brief explanations of the differences between the examples I listed:<br>
> 1. Docker: Docker is a container platform that is widely used for building, packaging, and deploying containerized applications. It is known for its ease of use, portability, and large ecosystem of tools and services.<br>
> 2. Kubernetes: Kubernetes is a container orchestration tool that helps manage and deploy containers at scale. It automates the deployment, scaling, and management of containerized applications across multiple hosts.<br>
>
> <span style="color:Gold">Bot:</span> The main differences between container software are in their architecture, feature sets, and use cases. Here are some brief explanations of the differences between the examples I listed:<br>
> 1. Docker: Docker is a container platform that is widely used for building, packaging, and deploying containerized applications. It is known for its ease of use, portability, and large ecosystem of tools and services.<br>
> 2. Kubernetes: Kubernetes is a container orchestration tool that helps manage and deploy containers at scale. It automates the deployment, scaling, and management of containerized applications across multiple hosts.<br>
