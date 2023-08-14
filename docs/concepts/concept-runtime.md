In Azure Machine Learning prompt flow, the execution of flows is facilitated through the use of runtimes.

# Runtimes

In prompt flow, runtimes serve as computing resources that enable customers to execute their flows seamlessly. A runtime is equipped with a pre-built Docker image that includes our built-in tools, ensuring that all necessary tools are readily available for execution.

Within the Azure Machine Learning workspace, users have the option to create a runtime using the pre-defined default environment. This default environment is set up to reference the pre-built Docker image, providing users with a convenient and efficient way to get started. We regularly update the default environment to ensure it aligns with the latest version of the Docker image.

For users seeking further customization, prompt flow offers the flexibility to create a custom execution environment. By utilizing our pre-built Docker image as a foundation, users can easily customize their environment by adding their preferred packages, configurations, or other dependencies. Once customized, the environment can be published as a custom environment within the Azure Machine Learning workspace, allowing users to create a runtime based on their custom environment.

In addition to flow execution, the runtime is also utilized to validate and ensure the accuracy and functionality of the tools incorporated within the flow, when users make updates to the prompt or code content.

Prompt flow offers two types of runtimes to customers: *Managed Online Deployment Runtime* and *Compute Instance Runtime*. Both runtime types provide the same capability for executing flows, but they differ in terms of scalability, resource sharing, user identity support, and ease of customizing the environment.

The table below outlines the key differences between these runtime types:

|                       | Managed online deployment runtime                            | Compute instance runtime                                     |
| --------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Underlying resource   | [Azure Machine Learning managed online endpoints](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online) | [Azure Machine Learning compute instance](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-instance) |
| Scalability           | Multi-nodes                                                  | Single node                                                  |
| Resource sharing      | Yes                                                          | No                                                           |
| User identity support | No                                                           | Yes                                                          |
| Ease of Customization | No                                                           | Yes                                                          |



## Next steps

- [Create runtimes](../how-to-guides/how-to-create-manage-runtime.md)

