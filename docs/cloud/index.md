# Cloud

Prompt flow streamlines the process of developing AI applications based on LLM, easing prompt engineering, prototyping, evaluating, and fine-tuning for high-quality products.

Transitioning to production, however, typically requires a comprehensive **LLMOps process**. This can often be a complex task, demanding high availability and security, particularly vital for large-scale team collaboration and lifecycle management when deploying to production.

To assist in this journey, we've introduced **Azure AI**, a **cloud-based platform** tailored for executing LLMOps, focusing on boosting productivity for enterprises.


<table>
    <tr>
        <td>
            <ul>
                <li>Private data access and controls</li>
                <li>Collaborative development</li>
                <li>Automating iterative experimentation and CI/CD</li>
                <li>Deployment and optimization</li>
                <li>Safe and Responsible AI</li>
            </ul>
        </td>
        <td>
            <img src="../media/cloud/azureml/llmops_cloud_value.png" width="60%">
        </td>
    </tr>
</table>

## Transitioning from local to cloud (Azure AI)

In prompt flow, You can develop your flow locally and then seamlessly transition to Azure AI. Here are a few scenarios where this might be beneficial:
| Scenario | Benefit | How to|
| --- | --- |--- |
| Collaborative development | Azure AI provides a cloud-based platform for flow development and management, facilitating sharing and collaboration across multiple teams, organizations, and tenants.| [Submit a run using pfazure](./azureai/quick-start.md), based on the flow file in your code base.|
| Processing large amounts of data in parallel pipelines | Transitioning to Azure AI allows you to use your flow as a parallel component in a pipeline job, enabling you to process large amounts of data and integrate with existing pipelines. | Learn how to [Use flow in Azure ML pipeline job](./azureai/use-flow-in-azure-ml-pipeline.md).|
| Large-scale Deployment | Azure AI allows for seamless deployment and optimization when your flow is ready for production and requires high availability and security. | Use `pf flow build` to deploy your flow to [Azure App Service](./azureai/deploy-to-azure-appservice.md).|
| Data Security and  Responsible AI Practices | If your flow handling sensitive data or requiring ethical AI practices, Azure AI offers robust security, responsible AI services, and features for data storage, identity, and access control. | Follow the steps mentioned in the above scenarios.|


For more resources on Azure AI, visit the cloud documentation site: [Build AI solutions with prompt flow](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/get-started-prompt-flow?view=azureml-api-2).

```{toctree}
:caption: AzureAI
:maxdepth: 1
azureai/quick-start
azureai/deploy-to-azure-appservice
azureai/use-flow-in-azure-ml-pipeline.md
azureai/faq
```