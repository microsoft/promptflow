# Chat with external functions

This flow covers how to use the LLM chat API in combination with external functions to extend the capabilities of GPT models. 

`tools` is an optional parameter in the Chat Completion API which can be used to provide function specifications. The purpose of this is to enable models to generate function arguments which adhere to the provided specifications. Note that the API will not actually execute any function calls. It is up to developers to execute function calls using model outputs.

Within the `tools` parameter, if the `functions` parameter is provided then by default the model will decide when it is appropriate to use one of the functions. The API can be forced to use a specific function by setting the `tool_choice` parameter to `{"type": "function", "function": {"name": "my_function"}}`. The API can also be forced to not use any function by setting the `tool_choice` parameter to `"none"`. If a function is used, the output will contain `"finish_reason": "tool_calls"` in the response, as well as a `tool_calls` object that has the name of the function and the generated function arguments.

You can refer to <a href='https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb' target='_blank'>openai sample</a> for more details.


## What you will learn

In this flow, you will learn how to use external functions with LLM chat models and how to compose function role message in prompt template.

## Prerequisites
Install dependencies:
```bash
pip install -r requirements.txt
```

## Getting started

### 1 prepare api_key env
- Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure OpenAI endpoint key in [.env](../.env) file. You can create one refer to this [example file](../.env.example).

### 2 understand how chat model choose function
```shell
# see how llm will chose functions
pf flow test --flow chat_with_tools.prompty --env --inputs question="What is the weather like in Boston?"
pf flow test --flow chat_with_tools.prompty --env --inputs sample.json
```

### 3 Start chatting with flow

```bash
# run e2e chat flow with question
pf flow test --flow flow:chat --env --inputs question="What is the weather like in Boston?"

# run chat flow with question & chat_history from sample.json
pf flow test --flow flow:chat --env --inputs sample.json
```

```shell
# chat using ui
pf flow test --flow flow:chat --env --ui
```

## References
- <a href='https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb' target='_blank'>OpenAI cookbook example</a>
- <a href='https://openai.com/blog/function-calling-and-other-api-updates?ref=upstract.com' target='_blank'>OpenAI function calling announcement</a> 
- <a href='https://platform.openai.com/docs/guides/gpt/function-calling' target='_blank'>OpenAI function calling doc</a>
- <a href='https://platform.openai.com/docs/api-reference/chat/create' target='_blank'>OpenAI function calling API</a>
