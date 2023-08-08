In Azure Machine Learning prompt flow, users have the capability to develop a LLM-based AI application by engaging in the stages of developing, testing, tuning, and deploying a flow. This comprehensive workflow allows users to harness the power of Large Language Models (LLMs) and create sophisticated AI applications with ease.

# Flows

A flow in prompt flow serves as an executable workflow that streamlines the development of your LLM-based AI application. It provides a comprehensive framework for managing data flow and processing within your application.

Within a flow, nodes take center stage, representing specific tools with unique capabilities. These nodes handle data processing, task execution, and algorithmic operations, with inputs and outputs. By connecting nodes, you establish a seamless chain of operations that guides the flow of data through your application.

To facilitate node configuration and fine-tuning, our user interface offers a notebook-like authoring experience. This intuitive interface allows you to effortlessly modify settings and edit code snippets within nodes. Additionally, a visual representation of the workflow structure is provided through a DAG (Directed Acyclic Graph) graph. This graph showcases the connectivity and dependencies between nodes, providing a clear overview of the entire workflow.

With the flow feature in prompt flow, you have the power to design, customize, and optimize the logic of your AI application. The cohesive arrangement of nodes ensures efficient data processing and effective flow management, empowering you to create robust and advanced applications.

## Flow types

Azure Machine Learning prompt flow offers three different flow types to cater to various user scenarios:

- **Standard flow**: Designed for general application development, the standard flow allows users to create a flow using a wide range of built-in tools for developing LLM-based applications. It provides flexibility and versatility for developing applications across different domains.
- **Chat flow**: Specifically tailored for conversational application development, the Chat flow builds upon the capabilities of the standard flow and provides enhanced support for chat inputs/outputs and chat history management. With native conversation mode and built-in features, users can seamlessly develop and debug their applications within a conversational context.
- **Evaluation flow**: Designed for evaluation scenarios, the evaluation flow enables users to create a flow that takes the outputs of previous flow runs as inputs. This flow type allows users to evaluate the performance of previous run results and output relevant metrics, facilitating the assessment and improvement of their models or applications.

## Next steps

- [Quick start](../quick-start.md)
- [Create standard flows](../how-to-guides/how-to-develop-a-standard-flow.md)
- [Create chat flows](../how-to-guides/how-to-develop-a-chat-flow.md)
- [Create evaluation flows](../how-to-guides/how-to-develop-an-evaluation-flow.md)