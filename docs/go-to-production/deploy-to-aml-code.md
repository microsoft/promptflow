# Deploy a flow to online endpoint for real-time inference with CLI and SDK (preview)

In this article, you'll learn to deploy your flow to a [managed online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints-vs-kubernetes-online-endpoints) or a [Kubernetes oneline endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints-vs-kubernetes-online-endpoints) for use in real-time inferencing with AzureML v2 CLI.

The starting point is that you have tested your flow properly, and feel confident that it is ready to be deployed to production. If you haven't done so, please refer to [test your flow](../test-your-flow.md) for more details. Then you'll learn how to create managed online endpoint and deployment, and how to use the endpoint for real-time inferencing.

- For **CLI** experience, all the sample yaml files can be found [here](https://aka.ms/pf-deploy-mir-cli).
- For **Python SDK** experience, sample notebook is [here](https://aka.ms/pf-deploy-mir-sdk).

## Prerequisites

- The Azure CLI and the ml extension to the Azure CLI. For more information, see [Install, set up, and use the CLI (v2)](https://learn.microsoft.com/azure/machine-learning/how-to-configure-cli?view=azureml-api-2).
- The Python SDK v2 for AzureML. See [Install the Python SDK v2 for Azure Machine Learning](https://learn.microsoft.com/python/api/overview/azure/ai-ml-readme).
- An AzureML workspace. If you don't have one, use the steps in the [Quickstart: Create workspace resources article](https://learn.microsoft.com/en-us/azure/machine-learning/quickstart-create-resources?view=azureml-api-2) to create one.
- Azure role-based access controls (Azure RBAC) are used to grant access to operations in Azure Machine Learning. To perform the steps in this article, your user account must be assigned the owner or contributor role for the Azure Machine Learning workspace, or a custom role allowing Microsoft.MachineLearningServices/workspaces/onlineEndpoints/*. If you use studio to create/manage online endpoints/deployments, you will need an additional permission "Microsoft.Resources/deployments/write" from the resource group owner. For more information, see [Manage access to an Azure Machine Learning workspace](https://learn.microsoft.com/azure/machine-learning/how-to-assign-roles?view=azureml-api-2).

### Virtual machine quota allocation for deployment
For managed online endpoints, Azure Machine Learning reserves 20% of your compute resources for performing upgrades. Therefore, if you request a given number of instances in a deployment, you must have a quota for `ceil(1.2 * number of instances requested for deployment) * number of cores for the VM SKU` available to avoid getting an error. For example, if you request 10 instances of a Standard_DS3_v2 VM (that comes with 4 cores) in a deployment, you should have a quota for 48 cores (12 instances * 4 cores) available. To view your usage and request quota increases, see [View your usage and quotas in the Azure portal](https://learn.microsoft.com/azure/machine-learning/how-to-manage-quotas?view=azureml-api-2#view-your-usage-and-quotas-in-the-azure-portal).

## Get the flow ready for deploy

Each flow will have a folder which contains codes/prompts, definition and other artifacts of the flow. If you have developed your flow with UI, you can download the flow folder from the flow details page. If you have developed your flow with CLI or SDK, you should have the flow folder already. 

This article will use the [sample flow "basic-chat"](../../examples/flows/chat/basic-chat) as an example to deploy to AzureML managed online endpoint. 

## Set default workspace

Use the following commands to set the default workspace and resource group for the CLI.

```Azure CLI
az account set --subscription <subscription ID>
az configure --defaults workspace=<Azure Machine Learning workspace name> group=<resource group>
```

## (optional) Register the flow as a model

In the online deployment, you can either refer to a registered model, or specify the model path (where to upload the model files from) inline. It is recommended to register the model and specify the model name and version in the deployment definition. Use the form `model:<model_name>:<version>`.

Following is a model definition example.

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/model.schema.json
name: basic-chat-model
path: ../../../../examples/flows/chat/basic-chat
description: register basic chat flow folder as a custom model
properties:
  # In AuzreML studio UI, endpoint detail UI Test tab needs this property to know it's from prompt flow
  azureml.promptflow.source_flow_id: basic-chat
  
  # Following are properties only for chat flow 
  # endpoint detail UI Test tab needs this property to know it's a chat flow
  azureml.promptflow.mode: chat
  # endpoint detail UI Test tab needs this property to know which is the input column for chat flow
  azureml.promptflow.chat_input: question
  # endpoint detail UI Test tab needs this property to know which is the output column for chat flow
  azureml.promptflow.chat_output: answer
```

Use `az ml model create --file model.yaml` to register the model to your workspace.

## Define the endpoint

To define an endpoint, you need to specify:

- **Endpoint name**: The name of the endpoint. It must be unique in the Azure region. For more information on the naming rules, see [managed online endpoint limits](https://learn.microsoft.com/azure/machine-learning/how-to-manage-quotas?view=azureml-api-2#azure-machine-learning-managed-online-endpoints).
- **Authentication mode**: The authentication method for the endpoint. Choose between key-based authentication and Azure Machine Learning token-based authentication. A key doesn't expire, but a token does expire. For more information on authenticating, see [Authenticate to an online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2).
Optionally, you can add a description and tags to your endpoint.
- Optionally, you can add a description and tags to your endpoint.
- If you want to deploy to a Kubernetes cluster (AKS or Arc enabled cluster)  which is attaching to your workspace, you can deploy the flow to be a **Kubernetes online endpoint**.

Following is an endpoint definition example.

::::{tab-set}

:::{tab-item} Managed online endpoint
:sync: Managed online endpoint

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineEndpoint.schema.json
name: basic-chat-endpoint
auth_mode: key
```

:::

:::{tab-item} Kubernetes online endpoint
:sync: Kubernetes online endpoint

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/kubernetesOnlineEndpoint.schema.json
name: basic-chat-endpoint
compute: azureml:<Kubernetes compute name>
auth_mode: key
```

:::

::::


| Key         | Description                                                                                                                                                                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `$schema`   | (Optional) The YAML schema. To see all available options in the YAML file, you can view the schema in the preceding code snippet in a browser.                                                                                                                   |
| `name`      | The name of the endpoint.                                               |
| `auth_mode` | Use `key` for key-based authentication. Use `aml_token` for Azure Machine Learning token-based authentication. To get the most recent token, use the `az ml online-endpoint get-credentials` command. |

If you create a Kubernetes online endpoint, you need to specify the following additional attributes:
| Key         | Description                                                                                                                                                                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compute`   | The Kubernetes compute target to deploy the endpoint to.                                                                                                     |

> [!IMPORTANT]
>
> By default, when you create an online endpoint, a system-assigned managed identity is automatically generated for you. You can also specify an existing user-assigned managed identity for the endpoint.
> You need to grant permissions to your endpoint identity so that it can access the Azure resources to perform inference. See [Grant permissions to your endpoint identity](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/how-to-deploy-for-real-time-inference?view=azureml-api-2#grant-permissions-to-the-endpoint) for more information.
>
> For more configurations of endpoint, see [managed online endpoint schema](https://learn.microsoft.com/azure/machine-learning/reference-yaml-endpoint-online?view=azureml-api-2).

### Define the deployment

A deployment is a set of resources required for hosting the model that does the actual inferencing. To deploy a flow, you must have:

- **Model files (or the name and version of a model that's already registered in your workspace).** In the example, we have a scikit-learn model that does regression.
- **A scoring script**, that is, code that executes the model on a given input request. The scoring script receives data submitted to a deployed web service and passes it to the model. The script then executes the model and returns its response to the client. The scoring script is specific to your model and must understand the data that the model expects as input and returns as output. In this example, we have a score.py file.
An environment in which your model runs. The environment can be a Docker image with Conda dependencies or a Dockerfile.
Settings to specify the instance type and scaling capacity.

Following is a deployment definition example.

::::{tab-set}

:::{tab-item} Managed online deployment
:sync: Managed online deployment

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
name: blue
endpoint_name: basic-chat-endpoint
model: azureml:basic-chat-model:1
  # You can also specify model files path inline
  # path: examples/flows/chat/basic-chat
environment: 
  image: mcr.microsoft.com/azureml/promptflow/promptflow-runtime:20230801.v1
  mcr.microsoft.com/azureml/promptflow/promptflow-runtime:20230801.v1
  # inference config is used to build a serving container for online deployments
  inference_config:
    liveness_route:
      path: /health
      port: 8080
    readiness_route:
      path: /health
      port: 8080
    scoring_route:
      path: /score
      port: 8080
instance_type: Standard_E16s_v3
instance_count: 1
environment_variables:

  # "compute" mode is the default mode, if you want to deploy to serving mode, you need to set this env variable to "serving"
  PROMPTFLOW_RUN_MODE: serving

  # for pulling connections from workspace
  PRT_CONFIG_OVERRIDE: deployment.subscription_id=<subscription_id>,deployment.resource_group=<resource_group>,deployment.workspace_name=<workspace_name>,deployment.endpoint_name=<endpoint_name>,deployment.deployment_name=<deployment_name>

  # (Optional) When there are multiple fields in the response, using this env variable will filter the fields to expose in the response.
  # For example, if there are 2 flow outputs: "answer", "context", and I only want to have "answer" in the endpoint response, I can set this env variable to '["answer"]'.
  # If you don't set this environment, by default all flow outputs will be included in the endpoint response.
  # PROMPTFLOW_RESPONSE_INCLUDED_FIELDS: '["category", "evidence"]'
```

:::

:::{tab-item} Kubernetes online deployment
:sync: Kubernetes online deployment

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/kubernetesOnlineDeployment.schema.json
name: blue
type: kubernetes
endpoint_name: basic-chat-endpoint
model: azureml:basic-chat-model:1
  # You can also specify model files path inline
  # path: examples/flows/chat/basic-chat
environment: 
  image: mcr.microsoft.com/azureml/promptflow/promptflow-runtime:20230801.v1
  mcr.microsoft.com/azureml/promptflow/promptflow-runtime:20230801.v1
  # inference config is used to build a serving container for online deployments
  inference_config:
    liveness_route:
      path: /health
      port: 8080
    readiness_route:
      path: /health
      port: 8080
    scoring_route:
      path: /score
      port: 8080
instance_type: <kubernetes custom instance type>
instance_count: 1
environment_variables:

  # "compute" mode is the default mode, if you want to deploy to serving mode, you need to set this env variable to "serving"
  PROMPTFLOW_RUN_MODE: serving

  # for pulling connections from workspace
  PRT_CONFIG_OVERRIDE: deployment.subscription_id=<subscription_id>,deployment.resource_group=<resource_group>,deployment.workspace_name=<workspace_name>,deployment.endpoint_name=<endpoint_name>,deployment.deployment_name=<deployment_name>

  # (Optional) When there are multiple fields in the response, using this env variable will filter the fields to expose in the response.
  # For example, if there are 2 flow outputs: "answer", "context", and I only want to have "answer" in the endpoint response, I can set this env variable to '["answer"]'.
  # If you don't set this environment, by default all flow outputs will be included in the endpoint response.
  # PROMPTFLOW_RESPONSE_INCLUDED_FIELDS: '["category", "evidence"]'
```
:::

::::

| Attribute      | Description                                                                                                                                                                                                                                                                                                                                                                                    |
|-----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Name           | The name of the deployment.                                                                                                                                                                                                                                                                                                                                                                    |
| Endpoint name  | The name of the endpoint to create the deployment under.   |
| Model          | The model to use for the deployment. This value can be either a reference to an existing versioned model in the workspace or an inline model specification.  |
| Environment    | The environment to host the model and code. It contains: <br>    - `image`<br>      - `inference_config`: is used to build a serving container for online deployments, including `liveness route`, `readiness_route`, and `scoring_route` .                                                             |
| Instance type  | The VM size to use for the deployment. For the list of supported sizes, see [Managed online endpoints SKU list](https://learn.microsoft.com/en-us/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list?view=azureml-api-2).  |
| Instance count | The number of instances to use for the deployment. Base the value on the workload you expect. For high availability, we recommend that you set the value to at least `3`. We reserve an extra 20% for performing upgrades. For more information, see [managed online endpoint quotas](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-quotas?view=azureml-api-2#azure-machine-learning-managed-online-endpoints).    |
|Environment variables| Following environment variables need to be set for endpoints deployed from a flow: <br> - (required) `PROMPTFLOW_RUN_MODE: serving`: specify the mode to serving <br> - (required) `PRT_CONFIG_OVERRIDE`: for pulling connections from workspace <br> - (optional) `PROMPTFLOW_RESPONSE_INCLUDED_FIELDS:`: When there are multiple fields in the response, using this env variable will filter the fields to expose in the response. <br> For example, if there are 2 flow outputs: "answer", "context", and if you only want to have "answer" in the endpoint response, you can set this env variable to '["answer"]'. <br> - <br>|

If you create a Kubernetes online deployment, you need to specify the following additional attributes:

| Attribute      | Description                                                                                                                                                                                                                                                                                                                                                                                    |
|-----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Type      | The type of the deployment. Set the value to `kubernetes`. |
| Instance type  | The instance type you have created in your kubernetes cluster to use for the deployment, represent the request/limit compute resource of the  deployment. For more detail, see [Create and manage instance type](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-kubernetes-instance-types?view=azureml-api-2&tabs=select-instancetype-to-trainingjob-with-cli%2Cselect-instancetype-to-modeldeployment-with-cli%2Cdefine-resource-to-modeldeployment-with-cli).  |                                                                                                                                                                                                                                                                                                                                |


### Deploy your online endpoint to Azure

To create the endpoint in the cloud, run the following code:

```Azure CLI
az ml online-endpoint create --file endpoint.yml
```

To create the deployment named `blue` under the endpoint, run the following code:

```Azure CLI
az ml online-deployment create --file blue-deployment.yml --all-traffic
```

This deployment might take up to 20 minutes, depending on whether the underlying environment or image is being built for the first time. Subsequent deployments that use the same environment will finish processing more quickly.

> [!TIP]
>
> * If you prefer not to block your CLI console, you may add the flag `--no-wait` to the command. However, this will stop the interactive display of the deployment status.

> [!IMPORTANT]
>
> The `--all-traffic` flag in the above `az ml online-deployment create` allocates 100% of the endpoint traffic to the newly created blue deployment. Though this is helpful for development and testing purposes, for production, you might want to open traffic to the new deployment through an explicit command. For example, `az ml online-endpoint update -n $ENDPOINT_NAME --traffic "blue=100"`.

### Check status of the endpoint and deployment

To check the status of the endpoint, run the following code:

```Azure CLI
az ml online-endpoint show -n basic-chat-endpoint
```

To check the status of the deployment, run the following code:

```Azure CLI
az ml online-deployment get-logs --name blue --endpoint basic-chat-endpoint
```

### Invoke the endpoint to score data by using your model

```Azure CLI
az ml online-endpoint invoke --name basic-chat-endpoint --request-file endpoints/online/model-1/sample-request.json
```

## Next steps

- Learn more about [managed online endpoint schema](https://learn.microsoft.com/azure/machine-learning/reference-yaml-endpoint-online?view=azureml-api-2) and [managed online deployment schema](https://learn.microsoft.com/azure/machine-learning/reference-yaml-deployment-managed-online?view=azureml-api-2).
- Learn more about how to [troubleshoot managed oneline endpoints](https://learn.microsoft.com/azure/machine-learning/how-to-troubleshoot-online-endpoints?view=azureml-api-2&tabs=cli).
- Once you improve your flow, and would like to deploy the improved version with safe rollout strategy, you can refer to [Safe rollout for online endpoints](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-safely-rollout-online-endpoints?view=azureml-api-2).