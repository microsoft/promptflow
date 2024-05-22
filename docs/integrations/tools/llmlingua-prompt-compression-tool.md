# LLMLingua Prompt Compression

## Introduction
LLMLingua Prompt Compression tool enables you to speed up large language model's inference and enhance large language model's perceive of key information, compress the prompt with minimal performance loss.

## Requirements
PyPI package: [`llmlingua-promptflow`](https://pypi.org/project/llmlingua-promptflow/).
- For Azure users: 
    follow [the wiki for AzureML](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/how-to-custom-tool-package-creation-and-usage?view=azureml-api-2#prepare-compute-session) or [the wiki for AI Studio](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/prompt-flow-tools/prompt-flow-tools-overview#custom-tools) to prepare the compute session.
- For local users: 
    ```
    pip install llmlingua-promptflow
    ```
    You may also want to install the [Prompt flow for VS Code extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

## Prerequisite
Create a MaaS deployment for large language model in Azure model catalog. Take the Llama model as an example, you can learn how to deploy and consume Meta Llama models with model as a service by  [the guidance for Azure AI Studio](https://learn.microsoft.com/azure/ai-studio/how-to/deploy-models-llama?tabs=llama-three#deploy-meta-llama-models-as-a-serverless-api) 
or
[the guidance for Azure Machine Learning Studio
](https://learn.microsoft.com/azure/machine-learning/how-to-deploy-models-llama?view=azureml-api-2&tabs=llama-three#deploy-meta-llama-models-with-pay-as-you-go).

## Inputs

The tool accepts the following inputs:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| prompt | string | The prompt that needs to be compressed. | Yes |
| myconn | CustomConnection | The created connection to a MaaS resource for calculating log probability. | Yes |
| rate | float | The maximum compression rate target to be achieved. Default value is 0.5. | No |

## Outputs

| Return Type | Description                                                          |
|-------------|----------------------------------------------------------------------|
| string      | The resulting compressed prompt.     |

## Sample Flows
Find example flows using the `llmlingua-promptflow` package [here](https://github.com/microsoft/promptflow/tree/main/examples/flows/integrations/llmlingua-prompt-compression).

## Contact
Please reach out to LLMLingua Team (<llmlingua@microsoft.com>) with any issues.