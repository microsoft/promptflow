# Named Entity Recognition

[Named Entity Recognition (NER)](https://en.wikipedia.org/wiki/Named-entity_recognition) is a Natural Language Processing (NLP) task. It involves identifying and classifying named entities (such as people, organizations, locations, date expressions, percentages, etc.) in a given text. This is a crucial aspect of NLP as it helps to understand the context and extract key information from the text.

 

This sample flow performs named entity recognition task using ChatGPT/GPT4 and prompts.

Tools used in this flow：
- `python` tool
- built-in `llm` tool

Connections used in this flow:
- `azure_open_ai` connection

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

Note in this example, we are using [chat api](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/chatgpt?pivots=programming-language-chat-completions), please use `gpt-35-turbo` or `gpt-4` model deployment.

Create connection if you haven't done that. Ensure you have put your azure open ai endpoint key in [azure_openai.yml](azure_openai.yml) file. 
```bash
# Override keys with --set to avoid yaml file changes
pf connection create -f ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Ensure you have created `azure_open_ai_connection` connection.
```bash
pf connection show -n azure_open_ai_connection
```


## Run flow in local

### Run locally with single line input

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
# test with specific input
pf flow test --flow . --inputs text='The phone number (321) 654-0987 is no longer in service' entity_type='phone number'
```

### run with multiple lines data

- create run
```bash
pf run create --flow . --data ./data.jsonl --stream
```


