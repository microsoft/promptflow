In prompt flow, you can utilize connections to securely manage credentials or secrets for external services.

# Connections

Connections are for storing information about how to access external services like LLMs: endpoint, api keys etc.

- In your local development environment, the connections are persisted in your local machine with keys encrypted.
- In Azure AI, connections can be configured to be shared across the entire workspace. Secrets associated with connections are securely persisted in the corresponding Azure Key Vault, adhering to robust security and compliance standards.

Prompt flow provides a variety of pre-built connections, including Azure Open AI, Open AI, etc. These pre-built connections enable seamless integration with these resources within the built-in tools. Additionally, you have the flexibility to create custom connection types using key-value pairs, empowering them to tailor the connections to their specific requirements, particularly in Python tools.

| Connection type                                              | Built-in tools                  |
| ------------------------------------------------------------ | ------------------------------- |
| [Azure Open AI](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service) | LLM or Python                   |
| [Open AI](https://openai.com/)                               | LLM or Python                   |
| [Cognitive Search](https://azure.microsoft.com/en-us/products/search) | Vector DB Lookup or Python      |
| [Serp](https://serpapi.com/)                                 | Serp API or Python              |
| [Serverless](https://learn.microsoft.com/en-us/azure/ai-studio/concepts/deployments-overview#deploy-models-with-model-as-a-service-maas)                                               | LLM or Python                   |
| Custom                                                       | Python                          |

By leveraging connections in prompt flow, you can easily establish and manage connections to external APIs and data sources, facilitating efficient data exchange and interaction within their AI applications.

## Next steps

- [Create connections](../how-to-guides/manage-connections.md)