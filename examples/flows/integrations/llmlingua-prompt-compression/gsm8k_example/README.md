# few shot example compression in GSM8k

## Flow description

A flow to test the accuracy of LLM (Large Language Model) in answering questions using a context that has been compressed.

GSM8K (Grade School Math 8K) is a dataset of 8.5K high quality, linguistically diverse grade school math word problems. The dataset was created to support the task of question answering on basic mathematical problems that require multi-step reasoning. The following steps are performed in this flow:
1. Read the `.txt` file of few-shot examples.
2. Use LLMLingua prompt compression tool to compress the GSM8K few-shot examples.
3. Test the LLM by using the compressed few-shot examples as context to determine if the answers are correct.

See the [`llmlingua-promptflow`](https://pypi.org/project/llmlingua-promptflow/) tool package reference documentation for further information.

Tools used in this flow:
- `python` tool.
- `LLMLingua Prompt Compression Tool` from the `llmlingua-promptflow` package.
- `prompt` tool.
- `LLM` tool.

Connections used in this flow:
- `Custom` connection.
- `AzureOpenAI` connection.

## Prerequisites

### Prompt flow SDK:
Install promptflow sdk and other dependencies:
```
pip install -r requirements.txt
```

Note: when using the Prompt flow SDK, it may be useful to also install the [`Prompt flow for VS Code`](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow) extension (if using VS Code).

### Azure AI/ML Studio:
Start an compute session. Required packages will automatically be installed from the `requirements.txt` file.

## Setup connections

### Custom connection
Create a connection to a MaaS resource for calculating log probability in Azure model catalog. You can use Llama, gpt-2, or other language models. 

Take the Llama model as an example, you can learn how to deploy and consume Meta Llama models with model as a service by  [the guidance for Azure AI Studio](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/deploy-models-llama?tabs=llama-three#deploy-meta-llama-models-with-pay-as-you-go) or [the guidance for Azure Machine Learning Studio
](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-models-llama?view=azureml-api-2&tabs=llama-three#deploy-meta-llama-models-with-pay-as-you-go).

The required keys to set are:
1. **api_url**
    - This value can be found at the previously created inferencing endpoint.
2. **api_key**
    - Ensure to set this as a secret value.
    - This value can be found at the previously created inferencing endpoint.

Create a Custom connection with `api_url` and `api_key`.

### AzureOpenAI connection
To use the `LLM` tool, you must have an [Azure OpenAI Service Resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal). Create one if necessary. From your Azure OpenAI Service Resource, obtain its `api_key` and `endpoint`.

Create a connection to your Azure OpenAI Service Resource. 
## Run flow

### Prompt flow SDK:
```
# Test with default input values in flow.dag.yaml:
pf flow test --flow .
```

### Azure AI/ML Studio:
Run flow.

## Contact
Please reach out to LLMLingua Team (<llmlingua@microsoft.com>) with any issues.