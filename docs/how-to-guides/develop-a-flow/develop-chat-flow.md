# Develop Chat flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

From this document, you can learn how to develop a chat flow by writing a flow yaml from scratch. You can 
find additional information about flow yaml schema in [Flow YAML Schema](../../reference/flow-yaml-schema-reference.md).

## Flow input data

The most important elements that differentiate a chat flow from a standard flow are **chat input** and **chat history**. A chat flow can have multiple inputs, but **chat history** and **chat input** are required inputs in chat flow.

- **Chat Input**: Chat input refers to the messages or queries submitted by users to the chatbot. Effectively handling chat input is crucial for a successful conversation, as it involves understanding user intentions, extracting relevant information, and triggering appropriate responses.

- **Chat History**: Chat history is the record of all interactions between the user and the chatbot, including both user inputs and AI-generated outputs. Maintaining chat history is essential for keeping track of the conversation context and ensuring the AI can generate contextually relevant responses. Chat history is a special type of chat flow input, that stores chat messages in a structured format.
    
    An example of chat history:
    ```python
    [
      {"inputs": {"question": "What types of container software there are?"}, "outputs": {"answer": "There are several types of container software available, including: Docker, Kubernetes"}},
      {"inputs": {"question": "What's the different between them?"}, "outputs": {"answer": "The main difference between the various container software systems is their functionality and purpose. Here are some key differences between them..."}},
    ] 
    ```

You can set **is_chat_input**/**is_chat_history** to **true** to add chat_input/chat_history to the chat flow.
```yaml
inputs:
  chat_history:
    type: list
    is_chat_history: true
    default: []
  question:
    type: string
    is_chat_input: true
    default: What is ChatGPT?
```


For more information see [develop the flow using different tools](./develop-standard-flow.md#flow-input-data).

## Develop the flow using different tools
In one flow, you can consume different kinds of tools. We now support built-in tool like 
[LLM](../../reference/tools-reference/llm-tool.md), [Python](../../reference/tools-reference/python-tool.md) and 
[Prompt](../../reference/tools-reference/prompt-tool.md) and 
third-party tool like [Serp API](../../reference/tools-reference/serp-api-tool.md), 
[Vector Search](../../reference/tools-reference/vector_db_lookup_tool.md), etc.

For more information see [develop the flow using different tools](./develop-standard-flow.md#develop-the-flow-using-different-tools).

## Chain your flow - link nodes together
Before linking nodes together, you need to define and expose an interface.

For more information see [chain your flow](./develop-standard-flow.md#chain-your-flow---link-nodes-together).


## Set flow output

**Chat output** is required output in the chat flow. It refers to the AI-generated messages that are sent to the user in response to their inputs. Generating contextually appropriate and engaging chat outputs is vital for a positive user experience.

You can set **is_chat_output** to **true** to add chat_output to the chat flow.

```yaml
outputs:
  answer:
    type: string
    reference: ${chat.output}
    is_chat_output: true
```
