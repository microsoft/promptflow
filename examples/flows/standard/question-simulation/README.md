# Question simulation:

This question simulation flow is used to generate suggestions for the next question based on the previous chat history. When the chat history seems like should be ended, then the flow output will be [STOP].

## Flow inputs
* __chat_history__: the previous chat_history, the format for it is as follows:
    [
      {
        "inputs": {
          "question": "Can you introduce something about large language model?"
        },
        "outputs": {
          "answer": "A large language model (LLM) is a type of language model that is distinguished by its ability to perform general-purpose language generation and understanding."
        }
      },
      {
        "inputs": {
          "question": "XXXXXX"
        },
        "outputs": {
          "answer": "XXXXXX"
        }
      }
    ]

* __question_count__: an integer is used to determine the number of questions to be generated. These generated question can be displayed in UX, allowing users to select the one that best suits their needs.

## Flow outputs
* If the conversation should go on, the output the suggestions for next question: multiple questions are seperated by '\n', for instance:
    "question": "question_1\nquestion_2\nquestion_3"
* If the conversation should ended, not more question will be generated, the output is a stop signal: [STOP]

## Tools used in this flow
- LLM tool
- Python tool
- Prompt tool


## 0. Setup connection
Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## 1. Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```