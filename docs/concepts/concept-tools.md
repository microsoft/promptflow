Tools are the fundamental building blocks of a [flow](./concept-flows.md).

Each tool is an executable unit, basically a function to performs various tasks including but not limited to:
- Accessing LLMs for various purposes
- Querying databases
- Getting information from search engines
- Pre/post processing of data

# Tools

Prompt flow provides 3 basic tools:
- [LLM](../reference/tools-reference/llm-tool.md): The LLM tool allows you to write custom prompts and leverage large language models to achieve specific goals, such as summarizing articles, generating customer support responses, and more.
- [Python](../reference/tools-reference/python-tool.md): The Python tool enables you to write custom Python functions to perform various tasks, such as fetching web pages, processing intermediate data, calling third-party APIs, and more.
- [Prompt](../reference/tools-reference/prompt-tool.md): The Prompt tool allows you to prepare a prompt as a string for more complex use cases or for use in conjunction with other prompt tools or python tools.

## More tools

Our partners also contributes other useful tools for advanced scenarios, here are some links:
- [Vector DB Lookup](../reference/tools-reference/vector_db_lookup_tool.md): vector search tool that allows users to search top k similar vectors from vector database.
- [Faiss Index Lookup](../reference/tools-reference/faiss_index_lookup_tool.md): querying within a user-provided Faiss-based vector store.

## Custom tools

You can create your own tools that can be shared with your team or anyone in the world. 
Learn more on [Custom tool package creation and usage](../how-to-guides/develop-custom-tool/custom-tool-package-creation-and-usage.md)

## Next steps

For more information on the available tools and their usage, visit the our [reference doc](../reference/index.md).