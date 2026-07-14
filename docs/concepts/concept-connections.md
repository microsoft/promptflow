In prompt flow, you can utilize connections to securely manage credentials or secrets for external services.

# Connections

Connections are for storing information about how to access external services like LLMs: endpoint, api keys etc.

- In your local development environment, the connections are persisted in your local machine with keys encrypted.
- In Azure AI, connections can be configured to be shared across the entire workspace. Secrets associated with connections are securely persisted in the corresponding Azure Key Vault, adhering to robust security and compliance standards.

Prompt flow provides a variety of pre-built connections, including Azure OpenAI, OpenAI, etc. These pre-built connections enable seamless integration with these resources within the built-in tools. Additionally, you have the flexibility to create custom connection types using key-value pairs, empowering them to tailor the connections to their specific requirements, particularly in Python tools.

| Connection type                                              | Built-in tools                  |
| ------------------------------------------------------------ | ------------------------------- |
| [Azure OpenAI](https://azure.microsoft.com/products/cognitive-services/openai-service) | LLM or Python                   |
| [OpenAI](https://openai.com/)                               | LLM or Python                   |
| [Cognitive Search](https://azure.microsoft.com/products/search) | Vector DB Lookup or Python      |
| [Serp](https://serpapi.com/)                                 | Serp API or Python              |
| [Serverless](https://learn.microsoft.com/azure/ai-studio/concepts/deployments-overview)                                               | LLM or Python                   |
| Custom                                                       | Python                          |

By leveraging connections in prompt flow, you can easily establish and manage connections to external APIs and data sources, facilitating efficient data exchange and interaction within their AI applications.

## OpenAI-compatible providers

`OpenAIConnection` can target OpenAI-compatible HTTP APIs by setting `base_url`. Prompt flow still uses the built-in OpenAI connection type and LLM tools; only the endpoint, API key, and model identifier change.

### Example: DaoXE

[DaoXE](https://daoxe.com) is a multi-model, multi-protocol AI API gateway. For OpenAI Chat Completions–compatible clients (including prompt flow's OpenAI connection), use:

| Field | Value |
| ----- | ----- |
| `base_url` | `https://daoxe.com/v1` |
| `api_key` | Your DaoXE API key from the dashboard |
| Model ID | Use an exact model identifier available on your DaoXE account (account-scoped; do not hard-code a global list) |

DaoXE also exposes other protocols outside this OpenAI connection path (for example OpenAI Responses and Anthropic Messages). Service availability does not include mainland China; check [daoxe.com](https://daoxe.com) for current access and model catalog details.

See [Manage connections](../how-to-guides/manage-connections.md#openai-compatible-endpoint-example-daoxe) for YAML, CLI, and SDK samples.

## Next steps

- [Create connections](../how-to-guides/manage-connections.md)
