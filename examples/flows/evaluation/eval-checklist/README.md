# Eval Check List
A example flow shows how to evaluate the answer pass user specified check list.

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Run flow

- Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

- Setup environment variables

Ensure you have put your azure open ai endpoint key in [.env](.env) file. You can create one refer to this [example file](.env.example).

```bash
cat .env
```

- Test flow
```bash
pf flow test --flow . --inputs answer='ChatGPT is a conversational AI model developed by OpenAI. It is based on the GPT-3 architecture and is designed to generate human-like responses to text inputs. ChatGPT is capable of understanding and responding to a wide range of topics and can be used for tasks such as answering questions, generating creative content, and providing assistance with various tasks. The model has been trained on a diverse range of internet text and is constantly being updated to improve its performance and capabilities. ChatGPT is available through the OpenAI API and can be accessed by developers and researchers to build applications and tools that leverage its capabilities.' statements='{\"correctness\":\"It contains a detailed explanation of ChatGPT.\"}'

```