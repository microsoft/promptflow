# Integrate with LangChain

Prompt Flow can also be used together with the [LangChain](https://python.langchain.com) python library, which is the framework for developing applications powered by LLMs, agents and dependency tools. In this document, we'll show you how to supercharge your LangChain development on our Prompt Flow.

![lc-flow](../media/langchain-integration/lc-flow.png)

## Benefits of LangChain integration

We consider the integration of LangChain and Prompt Flow as a powerful combination that can help you to build and test your custom language models with ease, especially in the case where one you may want to use LangChain modules to initially build your flow and then use our Prompt Flow to easily scale the experiments for bulk testing, evaluating then eventually deploying.

* For larger scale experiments - **Convert existed LangChain development in seconds.**<br>
If you have already developed demo prompt flow based on LangChain code locally, with the streamlined integration in Prompt Flow, you can easily convert it into a flow for further experimentation, for example you can conduct larger scale experiments based on larger data sets.
* For more familiar flow engineering - **Build prompt flow with ease based on your familiar Python SDK**.<br>If you are already familiar with the LangChain SDK and prefer to use its classes and functions directly, the intuitive flow building python node enables you to easily build flows based on your custom python code.

## How to convert LangChain code into flow

Assume that you already have your own LangChain code available locally, which is properly tested and ready for deployment. To convert it to a runnable flow on our platform, you need to follow the steps below.

### Prerequisites for environment and runtime

**NOTE:** Our base image has langchain v0.0.149 installed. To use another specific version, you need to create a customized environment.

#### Create a customized environment

For more libraries import, you need to customize environment based on our base image, which should contain all the dependency packages you need for your LangChain code. You can follow this guidance to use **docker context** to build your image, and [create the custom environment](./how-to-customize-environment-runtime.md#customize-environment-with-docker-context-for-runtime) based on it in AzureML workspace.

Then you can create a [Prompt Flow Runtime](./how-to-create-manage-runtime.md) based on this custom environment.

![runtime-custom-env](../media/langchain-integration/runtime-custom-env.png)

### Convert credentials to custom connection

Custom connection helps you to securely store and manage secret keys or other sensitive credentials required for interacting with LLM, rather than exposing them in environment variables hard code in your code and running on the cloud, protecting them from potential security breaches.

#### Create a Custom Connection

Create a custom connection that store all your LLM API KEY or other required credentials.

1. Go to prompt flow in your workspace, then go to **connections** tab.
2. Click **Add** and select **Custom**.
3. In the right panel, you can define your connection name, and you can add **multiple Key-Value** pairs to store your credentials and Keys.

For example：

![custom-conn1](../media/langchain-integration/custom-conn1.png)

![custom-conn2](../media/langchain-integration/custom-conn2.png)

**Note!**

* You can set one Key-Value pair as **secret** by **is secret** checked, which will be encrypted and stored in your key value.
* You can also set the whole connection as **workspace level key**, which will be shared to all members in the workspace. If not set as workspace level key, it can only be accessed by the creator.

Then this custom connection will be used to replace the key and credential you explicitly defined in LangChain code, if you already have a LangChain integration prompt flow, you can jump to​​​​​​​ [Configure connection, input and output](#configure-connection-input-and-output).

### LangChian code conversion to a runnable flow

All LangChain code can directly run in the python tools in your flow as long as your runtime environment contains the dependency packages, you can easily convert your LangChain code into a flow by following the steps below.

#### Create a flow with prompt tools and python tools

**Note:** There are two ways to convert your LangChain code into a flow.

* To simplify the conversion process, you can directly initialize the LLM model for invocation in a Python node by utilizing the LangChain integrated LLM library.
* Another approach is converting your LLM consuming from LangChain code to our LLM tool tools in the flow, for better further experimental management.

![lc-code-consume-llm](../media/langchain-integration/lc-code-consume-llm.png)

For quick conversion of LangChain code into a flow, we recommend two types of flow structures, based on the use case:

|| Types | Desc | Case |
|-------| -------- | -------- | -------- |
|**Type A**| A flow that includes both **prompt tools** and **python tools**| You can extract your prompt template from your code into a prompt node, then combine the remaining code in a single Python node or multiple Python tools. | This structure is ideal for who want to easily **tune the prompt** by running flow variants and then choose the optimal one based on evaluation results.|
|**Type B**| A flow that includes **python tools** only| You can create a new flow with python tools only, all code including prompt definition will run in python tools.| This structure is suitable for who do not need to explicit tune the prompt in workspace, but require faster batch testing based on larger scale datasets. |

For example, the type A flow is like:
![lc-flow-nodeA1](../media/langchain-integration/lc-flow-nodeA1.png)

![lc-flow-nodeA2](../media/langchain-integration/lc-flow-nodeA2.png)

For example, the type B flow is like:

![lc-flow-nodeB](../media/langchain-integration/lc-flow-nodeB.png)

To create a flow in Azure Machine Learning, you can go to your workspace, then click **Prompt Flow** in the left navigation, then click **Create** to create a new flow here. More detailed guidance on how to create a flow is introduced in Create a Flow.

#### Configure connection, input and output

After you have a properly structured flow and are done moving the code to specific tools, you need to configure the input, output, and connection settings in your flow and code to replace your original definitions.

To utilize a [custom connection](#create-a-custom-connection) that stores all the required keys and credentials, follow these steps:

1. In the python tools need to access LLM Key and other credentials, import custom connection library `from promptflow.connections import CustomConnection`.
2. Add an input parameter of type `connection` to the tool function.
3. Replace the environment variables that originally defined the key and credential with the corresponding key added in the connection.
4. Save and return to authoring page, and configure the connection parameter in the node input.

For example:

![custom-conn-python-node1](../media/langchain-integration/custom-conn-python-node1.png)

![custom-conn-python-node2](../media/langchain-integration/custom-conn-python-node2.png)

Before running the flow, configure the **node input and output**, as well as the overall **flow input and output**. This step is crucial to ensure that all the required data is properly passed through the flow and that the desired results are obtained.

## Related Resources

* [langchain.com](https://langchain.com)
* [Create a Custom Environment](./how-to-customize-environment-runtime.md#customize-environment-with-docker-context-for-runtime)
* [Create a Runtime](./how-to-create-manage-runtime.md)
