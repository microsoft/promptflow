# Use Tools with Chat Models

This flow covers how to use the LLM tool chat API in combination with external functions to extend the 
capabilities of GPT models. 

`tools` is an optional parameter in the <a href='https://platform.openai.com/docs/api-reference/chat/create' target='_blank'>Chat Completion API</a> which can be used to provide tool 
specifications. The purpose of this is to enable models to generate function arguments which adhere to the provided 
specifications. Note that the API will not actually execute any tool calls. It is up to developers to execute 
tool calls using model outputs. 

If the `tools` parameter is provided then by default the model will decide when it is appropriate to use one of the 
tools. The API can be forced to use a specific tool by setting the `tool_choice` parameter to 
`{"type": "function", "function": {"name": "<insert-function-name>"}}`. The API can also be forced to not use any tool by setting the `tool_choice` 
parameter to `"none"`. If a tool is used, the output will contain `"finish_reason": "tool_choice"` in the 
response, as well as a `tool_choice` object that has the name of the tool and the generated function arguments. 
You can refer to <a href='https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb' target='_blank'>openai sample</a> for more details.


## What you will learn

In this flow, you will learn how to use tools with LLM chat models and how to compose tool role message in prompt template.

## Tools used in this flow
- LLM tool
- Python tool

## Prerequisites
Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting started

### 1 Create connection for LLM tool to use
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of LLM tool supported connection types and fill in the configurations.

Currently, there are two connection types supported by LLM tool: "AzureOpenAI" and "OpenAI". If you want to use "AzureOpenAI" connection type, you need to create an Azure OpenAI service first. Please refer to [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service/) for more details. If you want to use "OpenAI" connection type, you need to create an OpenAI account first. Please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> --name open_ai_connection
```

Note in [flow.dag.yaml](flow.dag.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection 
pf connection show --name open_ai_connection
```

### 2 Start chatting

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow . 

# run chat flow with new question
pf flow test --flow . --inputs question="What's the current weather like in San Francisco, Tokyo and Paris in Fahrenheit?"

# start a interactive chat session in CLI
pf flow test --flow . --interactive

# start a interactive chat session in CLI with verbose info
pf flow test --flow . --interactive --verbose
```

## References
- <a href='https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb' target='_blank'>OpenAI cookbook example</a>
- <a href='https://openai.com/blog/function-calling-and-other-api-updates?ref=upstract.com' target='_blank'>OpenAI function calling announcement</a> 
- <a href='https://platform.openai.com/docs/guides/function-calling' target='_blank'>OpenAI function calling doc</a>
- <a href='https://platform.openai.com/docs/api-reference/chat/create' target='_blank'>OpenAI tools API</a>
