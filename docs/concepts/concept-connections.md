In Azure Machine Learning prompt flow, you can utilize connections to effectively manage credentials or secrets for APIs and data sources.

# Connections

Connections in prompt flow play a crucial role in establishing connections to remote APIs or data sources. They encapsulate essential information such as endpoints and secrets, ensuring secure and reliable communication.

In the Azure Machine Learning workspace, connections can be configured to be shared across the entire workspace or limited to the creator. Secrets associated with connections are securely persisted in the corresponding Azure Key Vault, adhering to robust security and compliance standards.

Prompt flow provides a variety of pre-built connections, including Azure Open AI, Open AI, and Azure Content Safety. These pre-built connections enable seamless integration with these resources within the built-in tools. Additionally, users have the flexibility to create custom connection types using key-value pairs, empowering them to tailor the connections to their specific requirements, particularly in Python tools.

| Connection type                                              | Built-in tools                  |
| ------------------------------------------------------------ | ------------------------------- |
| [Azure Open AI](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service) | LLM or Python                   |
| [Open AI](https://openai.com/)                               | LLM or Python                   |
| [Azure Content Safety](https://aka.ms/acs-doc)               | Content Safety (Text) or Python |
| [Cognitive Search](https://azure.microsoft.com/en-us/products/search) | Vector DB Lookup or Python      |
| [Serp](https://serpapi.com/)                                 | Serp API or Python              |
| Custom                                                       | Python                          |

By leveraging connections in prompt flow, users can easily establish and manage connections to external APIs and data sources, facilitating efficient data exchange and interaction within their AI applications.

## Next steps

- [Create connections](../quick-start.md)