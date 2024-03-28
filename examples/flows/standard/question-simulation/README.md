# Question simulation:

This question simulation flow is used to generate suggestions for the next question based on the previous chat history.

## Flow inputs
* chat_history (list): the previous chat_history, the format for it is as follows:
    [
      {
        "inputs": {
          "question": "XXXXXX"
        },
        "outputs": {
          "answer": "XXXXXX"
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

* question_count (int): an integer is used to determine the number of questions to be generated. These generated question can be displayed in UX, allowing users to select the one that best suits their needs.

## Flow outputs
* question (str): multiple questions are seperated by '\n', for instance:
    "question": "question_1\nquestion_2\nquestion_3"
* Stop signal is [STOP], when the output is [STOP], it means the conversation have arrived to end. No more questions will be generated. 

## Tools used in this flow
- LLM tool
- Python tool
- Prompt tool


## 0. Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base> name=promptflow-ci-sweden-central api_version=2023-07-01-preview
```

## 1. Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```