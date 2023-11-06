# Custom Tools 

This section contains documentation for custom tools created by the community to extend prompt flow's capabilities for specific use cases. These tools are developed following the guide on [Creating and Using Tool Packages](../../how-to-guides/develop-a-tool/create-and-use-tool-package.md). They are not officially maintained or endorsed by the prompt flow team. For questions or issues when using a tool, please use the support contact in the table below.

## Tool Package Index 

The table below provides an index of custom tool packages. The columns contain:

- **Package Name:** The name of the tool package. Links to the PYPI package page. To install the custom tool package, please execute the command `pip install <package name>`.
- **Tool Name:** Tools in the package. Links to the tool documentation.
- **Description:** A short summary of what the tool does.
- **Support Contact:** The Github account to contact for support and reporting new issues.

| Package Name | Tool Name | Description | Support Contact |  
|-|-|-|-|
|[promptflow-vectordb](https://pypi.org/project/promptflow-vectordb/)| [Vector DB Lookup](./vector_db_lookup_tool.md) | Search vector based query from existing Vector Database. | dans-msft, Adarsh-Ramanathan |
|| [Faiss Index Lookup](./faiss_index_lookup_tool.md) | Search vector based query from the FAISS index file. | dans-msft, Adarsh-Ramanathan |
|[promptflow-contentsafety](https://pypi.org/project/promptflow-contentsafety/)| [Content Safety (Text)](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/tools-reference/content-safety-text-tool?view=azureml-api-2) | Use Azure Content Safety to detect harmful content. | asmeyyh, jr-MS |

```{toctree}
:maxdepth: 1
:hidden:

vector_db_lookup_tool
faiss_index_lookup_tool
```
