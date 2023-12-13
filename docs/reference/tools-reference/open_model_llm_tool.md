# Open Model LLM

## Introduction

The Open Model LLM tool enables the utilization of a variety of Open Model and Foundational Models, such as [Falcon](https://ml.azure.com/models/tiiuae-falcon-7b/version/4/catalog/registry/azureml) and [Llama 2](https://ml.azure.com/models/Llama-2-7b-chat/version/14/catalog/registry/azureml-meta), for natural language processing in Azure ML Prompt Flow.

Here's how it looks in action on the Visual Studio Code prompt flow extension. In this example, the tool is being used to call a LlaMa-2 chat endpoint and asking "What is CI?".

![Screenshot of the Open Model LLM On VScode Prompt Flow extension](../../media/reference/tools-reference/open_model_llm_on_vscode_promptflow.png)

This prompt flow tool supports two different LLM API types:

- **Chat**: Shown in the example above. The chat API type facilitates interactive conversations with text-based inputs and responses.
- **Completion**: The Completion API type is used to generate single response text completions based on provided prompt input.

## Quick Overview: How do I use Open Model LLM Tool?

1. Choose a Model from the AzureML Model Catalog and get it deployed.
2. Connect to the model deployment.
3. Configure the open model llm tool settings.
4. Prepare the Prompt with [guidance](./prompt-tool.md#how-to-write-prompt).
5. Run the flow.

## Prerequisites: Model Deployment

1. Pick the model which matched your scenario from the [Azure Machine Learning model catalog](https://ml.azure.com/model/catalog).
2. Use the "Deploy" button to deploy the model to a AzureML Online Inference endpoint.
2.1. Use one of the Pay as you go deployment options.

More detailed instructions can be found here [Deploying foundation models to endpoints for inferencing.](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-foundation-models?view=azureml-api-2#deploying-foundation-models-to-endpoints-for-inferencing)

## Prerequisites: Connect to the Model

In order for prompt flow to use your deployed model, you will need to connect to it. There are several ways to connect.

### 1. Endpoint Connections

Once associated to a AzureML or Azure AI Studio workspace, the Open Model LLM tool can use the endpoints on that workspace.

1. **Using AzureML or Azure AI Studio workspaces**: If you are using prompt flow in one of the web page based browsers workspaces, the online endpoints available on that workspace will automatically who up.

2. **Using VScode or Code First**: If you are using prompt flow in VScode or one of the Code First offerings, you will need to connect to the workspace. The Open Model LLM tool uses the azure.identity DefaultAzureCredential client for authorization. One way is through [setting environment credential values](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.environmentcredential?view=azure-python).

### 2. Custom Connections

The Open Model LLM tool uses the CustomConnection. Prompt flow supports two types of connections:

1. **Workspace Connections** - These are connections which are stored as secrets on an Azure Machine Learning workspace. While these can be used, in many places, the are commonly created and maintained in the Studio UI.

2. **Local Connections** - These are connections which are stored locally on your machine. These connections are not available in the Studio UX's, but can be used with the VScode extension.

Instructions on how to create a workspace or local Custom Connection [can be found here.](../../how-to-guides/manage-connections.md#create-a-connection)

The required keys to set are:

1. **endpoint_url**
    - This value can be found at the previously created Inferencing endpoint.
2. **endpoint_api_key**
    - Ensure to set this as a secret value.
    - This value can be found at the previously created Inferencing endpoint.
3. **model_family**
    - Supported values: LLAMA, DOLLY, GPT2, or FALCON
    - This value is dependent on the type of deployment you are targeting.

## Running the Tool: Inputs

The Open Model LLM tool has a number of parameters, some of which are required. Please see the below table for details, you can match these to the screen shot above for visual clarity.

| Name | Type | Description | Required |
|------|------|-------------|----------|
| api | string | This is the API mode and will depend on the model used and the scenario selected. *Supported values: (Completion \| Chat)* | Yes |
| endpoint_name | string | Name of an Online Inferencing Endpoint with a supported model deployed on it. Takes priority over connection. | No |
| temperature | float | The randomness of the generated text. Default is 1. | No |
| max_new_tokens | integer | The maximum number of tokens to generate in the completion. Default is 500. | No |
| top_p | float | The probability of using the top choice from the generated tokens. Default is 1. | No |
| model_kwargs | dictionary | This input is used to provide configuration specific to the model used. For example, the Llama-02 model may use {\"temperature\":0.4}. *Default: {}* | No |
| deployment_name | string | The name of the deployment to target on the Online Inferencing endpoint. If no value is passed, the Inferencing load balancer traffic settings will be used. | No |
| prompt | string | The text prompt that the language model will use to generate it's response. | Yes |

## Outputs

| API        | Return Type | Description                              |
|------------|-------------|------------------------------------------|
| Completion | string      | The text of one predicted completion     |
| Chat       | string      | The text of one response int the conversation |

## Deploying to an Online Endpoint

When deploying a flow containing the Open Model LLM tool to an online endpoint, there is an additional step to setup permissions. During deployment through the web pages, there is a choice between System-assigned and User-assigned Identity types. Either way, using the Azure Portal (or a similar functionality), add the "Reader" Job function role to the identity on the Azure Machine Learning workspace or Ai Studio project which is hosting the endpoint. The prompt flow deployment may need to be refreshed.
