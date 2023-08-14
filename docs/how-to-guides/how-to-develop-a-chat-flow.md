# Develop a chat flow

Chat flow is designed for conversational application development, building upon the capabilities of standard flow and providing enhanced support for chat inputs/outputs and chat history management. With chat flow, you can easily create a chatbot that handles chat input and output.

Before reading this article, it is recommended that you first learn [Develop a standard Flow ](how-to-develop-a-standard-flow.md).

## Create a chat flow
To create a chat flow, you can **either** clone an existing chat flow sample from the Prompt Flow Gallery **or** create a new chat flow from scratch. For a quick start, you can clone a chat flow sample and learn how it works.

![create-chat-flow](../media/how-to-develop-a-chat-flow/create-chat-flow.png)

In chat flow authoring page, the chat flow is tagged with a "chat" label to distinguish it from standard flow and evaluation flow. To test the chat flow, click "Chat" button to trigger a chat box for conversation. 

![introduce-chat-flow-input-and-history-and-output](../media/how-to-develop-a-chat-flow/chat-input-output.png)

## Develop a chat flow

### Develop flow inputs and outputs
The most important elements that differentiate a chat flow from a standard flow are **Chat Input**, **Chat History**, and **Chat Output**.  
- **Chat Input**: Chat input refers to the messages or queries submitted by users to the chatbot. Effectively handling chat input is crucial for a successful conversation, as it involves understanding user intentions, extracting relevant information, and triggering appropriate responses. 
- **Chat History**: Chat history is the record of all interactions between the user and the chatbot, including both user inputs and AI-generated outputs. Maintaining chat history is essential for keeping track of the conversation context and ensuring the AI can generate contextually relevant responses. Chat History is a special type of chat flow input, that stores chat messages in a structured format. 
- **Chat Output**: Chat output refers to the AI-generated messages that are sent to the user in response to their inputs. Generating contextually appropriate and engaging chat outputs is vital for a positive user experience. 

A chat flow can have multiple inputs, but Chat History and Chat Input are **required** inputs in chat flow.
- In the chat flow Inputs section, the selected flow input serves as the Chat Input. The most recent chat input message in the chat box is backfilled to the Chat Input value.

  ![chat-input](../media/how-to-develop-a-chat-flow/chat-input.png)
- The `chat_history` input field in the Inputs section is reserved for representing Chat History. All interactions in the chat box, including user chat inputs, generated chat outputs, and other flow inputs and outputs, are stored in  `chat_history`. It is structured as a list of inputs and outputs as shown below: 
    ```json
    [
    {
        "inputs": {
        "<flow input 1>": "xxxxxxxxxxxxxxx",
        "<flow input 2>": "xxxxxxxxxxxxxxx",
        "<flow input N>""xxxxxxxxxxxxxxx"
        },
        "outputs": {
        "<flow output 1>": "xxxxxxxxxxxx",
        "<flow output 2>": "xxxxxxxxxxxxx",
        "<flow output M>": "xxxxxxxxxxxxx"
        }
    },
    {
        "inputs": {
        "<flow input 1>": "xxxxxxxxxxxxxxx",
        "<flow input 2>": "xxxxxxxxxxxxxxx",
        "<flow input N>""xxxxxxxxxxxxxxx"
        },
        "outputs": {
        "<flow output 1>": "xxxxxxxxxxxx",
        "<flow output 2>": "xxxxxxxxxxxxx",
        "<flow output M>": "xxxxxxxxxxxxx"
        }
    }
    ]
    ```
    In this chat flow example, the Chat History is generated as shown below.
    ![chat-history](../media/how-to-develop-a-chat-flow/chat-history.png)


A chat flow can have multiple flow outputs, but Chat Output is a **required** output for a chat flow. In the chat flow Outputs section, the selected output is used as the Chat Output.

### Author prompt with Chat History

Incorporating Chat History into your prompts is essential for creating context-aware and engaging chatbot responses. In your prompts, you can reference the `chat_history` input to retrieve past interactions. This allows you to reference previous inputs and outputs to create contextually relevant responses. 

Use [for-loop grammar of Jinja language](https://jinja.palletsprojects.com/en/3.1.x/templates/#for) to display a list of inputs and outputs from `chat_history`.  

```jinja
{% for item in chat_history %}
user:
{{item.inputs.question}}
assistant:
{{item.outputs.answer}}
{% endfor %}
```

## Test a chat flow

Testing your chat flow is a crucial step in ensuring that your chatbot responds accurately and effectively to user inputs. There are two primary methods for testing your chat flow: using the chat box for individual testing or creating a bulk test for larger datasets.

### Test with the chat box
The chat box provides an interactive way to test your chat flow by simulating a conversation with your chatbot. To test your chat flow using the chat box, follow these steps:
1. Click the "Chat" button to open the chat box.
2. Type your test inputs into the chat box and press Enter to send them to the chatbot.
3. Review the chatbot's responses to ensure they are contextually appropriate and accurate.

### Create a bulk test

Bulk test enables you to test your chat flow using a larger dataset, ensuring your chatbot's performance is consistent and reliable across a wide range of inputs. Thus, bulk test is ideal for thoroughly evaluating your chat flow's performance, identifying potential issues, and ensuring the chatbot can handle a diverse range of user inputs. 

To create a bulk test for your chat flow, you should prepare a dataset containing multiple data samples. Ensure that each data sample includes all the fields defined in the flow input, such as chat_input, chat_history, etc.   This dataset should be in a structured format, such as a CSV, TSV or JSON file. JSONL format is recommended for test data with chat_history. For more information about how to create bulk test, see [Submit Bulk Test and Evaluate a Flow](./how-to-bulk-test-evaluate-flow.md).



