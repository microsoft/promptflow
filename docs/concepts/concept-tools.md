Tools are the fundamental building blocks of a [flow](./concept-flows.md).

Each tool is an executable unit, basically a function to performs various tasks including but not limited to:
- Accessing LLMs for various purposes
- Querying databases
- Getting information from search engines
- Pre/post processing of data

# Tools

Prompt flow provides 3 basic tools:
- LLM: The LLM tool allows you to write custom prompts and leverage large language models to achieve specific goals, such as summarizing articles, generating customer support responses, and more.
- Python: The Python tool enables you to write custom Python functions to perform various tasks, such as fetching web pages, processing intermediate data, calling third-party APIs, and more.
- Prompt: The Prompt tool allows you to prepare a prompt as a string for more complex use cases or for use in conjunction with other prompt tools or python tools.

## More tools

// TODO: add links to vector db tools and cognitive services tools

## Custom tools

You can create your own tools that can be shared with your team or anyone in the world.
// TODO: add link to custom tool doc

## Next steps

For more information on the tools and their usage, visit the following resources:

- [Prompt tool](../reference/tools-reference/prompt-tool.md)
- [LLM tool](../reference/tools-reference/llm-tool.md)
- [Python tool](../reference/tools-reference/python-tool.md)
