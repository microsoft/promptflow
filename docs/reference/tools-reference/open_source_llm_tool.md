# Open Source LLM

## Introduction

The Prompt flow Open Source LLM tool enables you to utilize a variety of Open Source and Foundational Models, such as [Falcon](https://aka.ms/AAlc25c) or [Llama 2](https://aka.ms/AAlc258) for natural language processing, in PromptFlow.

This Prompt flow supports two different LLM API types:

- **Completion**: to generate text based on provided prompts.
- **Chat**: to facilitate interactive conversations with text-based inputs and responses.

## Prerequisite

1. Pick the model to use with from the [Azure Machine Learning model catalog](https://ml.azure.com/model/catalog).
2. Use the "Deploy" button to deploy the model to AzureML Inference endpoint.

More detailed instructions can be found here [Deploying foundation models to endpoints for inferencing.](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-foundation-models?view=azureml-api-2#deploying-foundation-models-to-endpoints-for-inferencing)

## **Connections**

Setup connections to provisioned resources in prompt flow.

| Type        | Name     | API KEY  | API Type | API Version |
|-------------|----------|----------|----------|-------------|
| CustomConnection | Required | Required | -        | -           |

Instructions to create a Custom Connection [can be found here.](https://microsoft.github.io/promptflow/how-to-guides/manage-connections.html#create-a-connection)

The keys to set are:

1. **endpoint_url**
   - This value can be found at the previously created Inferencing endpoint.
2. **endpoint_api_key**
   - Ensure to set this as a secret value.
   - This value can be found at the previously created Inferencing endpoint.
3. **model_family**
   - Supported values: LLAMA, DOLLY, GPT2, or FALCON
   - This value is dependent on the type of deployment you are targetting.

*These values can be found at the previously created Inferencing endpoint.*

## Inputs

| Name                   | Type        | Description                                                                             | Required |
|------------------------|-------------|-----------------------------------------------------------------------------------------|----------|
| api | string | this will be Completion or Chat, depending on the scenario selected | Yes |
| connection | CustomConnection | the name of the connection which points to the Inferencing endpoint | Yes |
| model_kwargs | dictionary | generic model configuration values, for example temperature | Yes |
| deployment_name | string | the name of the deployment to target on the MIR endpoint. If no value is passed, the MIR load balancer settings will be used. | No |
| prompt | string | text prompt that the language model will complete | Yes |

## Outputs

| API        | Return Type | Description                              |
|------------|-------------|------------------------------------------|
| Completion | string      | The text of one predicted completion     |
| Chat       | string      | The text of one response of conversation |

## How to use Open Source LLM Tool?

1. Choose a Model from the catalog and deploy.
2. Setup and select the connections to model deployment.
3. Configure the model api and its parameters
4. Prepare the Prompt with [guidance](prompt-tool.md#how-to-write-prompt).
