# Deploy a flow as a managed online endpoint for real-time inference

After you build a flow and test it properly, you may want to deploy it as an endpoint so that you can invoke the endpoint for real-time inference.

In this article, you'll learn how to deploy a flow as a managed online endpoint for real-time inference. The steps you'll take are:

- [Test your flow and get it ready for deployment](#build-the-flow-and-get-it-ready-for-deployment)
- [Create an online endpoint](#create-an-online-endpoint)
- [Grant permissions to the endpoint](#grant-permissions-to-the-endpoint)
- [Test the endpoint](#test-the-endpoint-with-sample-data)
- [Consume the endpoint](#consume-the-endpoint)

## Prerequisites

1. Learn [how to build and test a flow in the prompt flow](../quick-start.md).

1. Have basic understanding on managed online endpoints. Managed online endpoints work with powerful CPU and GPU machines in Azure in a scalable, fully managed way that frees you from the overhead of setting up and managing the underlying deployment infrastructure. For more information on managed online endpoints, see [What are Azure Machine Learning endpoints?](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2#managed-online-endpoints).

1. Azure role-based access controls (Azure RBAC) are used to grant access to operations in Azure Machine Learning. To be able to deploy an endpoint in prompt flow, your user account must be assigned the **AzureML Data scientist** or role with more privileges for the **Azure Machine Learning workspace**.


## Build the flow and get it ready for deployment

If you already completed the [Quick start guide](../quick-start.md), you've already tested the flow properly by submitting bulk tests and evaluating the results.

If you didn't complete the tutorial, you'll need to build a flow. Testing the flow properly by bulk tests and evaluation before deployment is a recommended best practice.

We'll use the sample flow **Web Classification** as example to show how to deploy the flow. This sample flow is a standard flow. Deploying chat flows is similar. Evaluation flow does not support deployment.

> [!NOTE]
> 
> Currently prompt flow only supports **single deployment** of managed online endpoints, so we will simplify the *deployment* configuration in the UI.
> 

## Create an online endpoint

Now that you have built a flow and tested it properly, it's time to create your online endpoint for real-time inference. 

The prompt flow supports you to deploy endpoints from a flow, or a bulk test run. Testing your flow before deployment is recommended best practice.

1. In the flow authoring page or run detail page, select **Deploy**.

    |Flow authoring page|Run detail page|
    |---|---|
    |![flow-authoring-page](../media/how-to-deploy-for-real-time-inference/deploy-flow-authoring-page.png)| ![run-detail-page](../media/how-to-deploy-for-real-time-inference/deploy-run-detail-page.png)|

1. A wizard for you to configure the endpoint occurs and include following steps.
   
    ### Endpoint

    ![deploy-wizard](../media/how-to-deploy-for-real-time-inference/deploy-wizard.png)

    This step allows you to configure the basic settings of an endpoint.

    You can select whether you want to deploy a new endpoint or update an existing endpoint. Select **New** means that a new endpoint will be created and the current flow will be deployed to the new endpoint.Select **Existing** means that the current flow will be deployed to an existing endpoint and replace the previous deployment. 
    
    You can also add description and tags for your to better identify the endpoint.

    #### Authentication type

    The authentication method for the endpoint. Key-based authentication provides a primary and secondary key that does not expire. Azure ML token-based authentication provides a token that periodically refreshes automatically. For more information on authenticating, see [Authenticate to an online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2&tabs=azure-cli).

    #### Identity type

    The endpoint needs to access Azure resources such as the Azure Container Registry or your workspace connections for inferencing. You can allow the endpoint permission to access Auzre resources via giving permission to its managed identity. 
    
    System-assigned identity will be auto-created after your endpoint is created, while user-assigned identity is created by user. [Learn more about managed identities.](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview?view=azureml-api-2)

    Select the identity you want to use, and you will notice a warning message to remind you to grant correct permissions to the identity after the endpoint is created.

    You can continue to configure the endpoint in wizard, as the endpoint creation will take some time. Make sure you grant permissions to the identity after the endpoint is created. See detailed guidance in [Grant permissions to the endpoint](#grant-permissions-to-the-endpoint).

    #### Allow sharing sample input data for testing purpose only

    If the checkbox is selected, the first row of your input data will be used as sample input data for testing the endpoint later.

    ### Connections

    In this step, you can view all connections within your flow, and change connections used by the endpoint when it performs inference later.
      ![connection](../media/how-to-deploy-for-real-time-inference/connection.png)

    ### Compute

    In this step, you can select the virtual machine size and instance count for your deployment.

    > [!NOTE]
    >
    > For **Virtual machine**, to ensure that your endpoint can serve smoothly, it’s better to select a virtual machine SKU with more than 8GB of memory.  For the list of supported sizes, see [Managed online endpoints SKU list](https://learn.microsoft.com/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list?view=azureml-api-2).
    >
    > For **Instance count**, Base the value on the workload you expect. For high availability, we recommend that you set the value to at least 3. We reserve an extra 20% for performing upgrades. For more information, see [managed online endpoints quotas](https://learn.microsoft.com/azure/machine-learning/how-to-manage-quotas?view=azureml-api-2#azure-machine-learning-managed-online-endpoints).


  1. Once you configured and reviewed all the steps above, you can select **Create** to finish the creation.

  > [!NOTE]
  > 
  > Expect the endpoint creation to take approximately several minutes.


## Check the status of the endpoint


There will be notification after you finish the deploy wizard. After the endpoint is created, you can select **Deploy details** in the notification to endpoint detail page.

You can also select **View endpoints** in your flow detail page, and view all endpoints deployed from the flow, or from the runs of this flow.

![view-endpoint-of-flow](../media/how-to-deploy-for-real-time-inference/view-endpoint-of-flow.png)

You can also directly go to the **Endpoints** page in the studio, and check the status of the endpoint you deployed.

![view-endpoint-detail](../media/how-to-deploy-for-real-time-inference/successful-deployment.png)

## Grant permissions to the endpoint

  > [!IMPORTANT]
    >
    > After you finish creating the endpoint and **before you test or consume the endpoint**, make sure you have granted correct permissions by adding role assignment to the managed identity of the endpoint. Otherwise, the endpoint will fail to perform inference due to lacking of permissions.
    >
    > Granting permissions (adding role assignment) is only enabled to the **Owner** of the speicifc Azure resources. You may need to ask your IT admin for help.

Following are the roles you need to assign to the managed identity of the endpoint, and why the permission of such role is needed.

For **System-assigned** identity:

|Resource|Role|Why it's needed|
|---|---|---|
|Azure Machine Learning Workspace|**AzureML Data Scientist** role **OR** a customized role with “Microsoft.MachineLearningServices/workspaces/connections/listsecrets/action” | Get workspace connections. |
|(Optional) Workspace default storage|* Storage Blob Data Contributor<br> * Storage Table Data Contributor| Enable tracing data including node level outputs/trace/logs when performing inference. Currently it's not required.|

For **User-assigned** identity:

|Resource|Role|Why it's needed|
|---|---|---|
|Azure Machine Learning Workspace|**AzureML Data Scientist** role **OR** a customized role with “Microsoft.MachineLearningServices/workspaces/connections/listsecrets/action” | Get workspace connections|
|Workspace container registry |Acr pull |Pull container image |
|Workspace default storage| Storage Blob Data Reader| Load model from storage |
|(Optional) Azure Machine Learning Workspace|Workspace metrics writer| After you deploy then endpoint, if you want to monitor the endpoint related metrics like CPU/GPU/Disk/Memory utilization, you need to give this permission to the identity.|
|(Optional) Workspace default storage|* Storage Blob Data Contributor<br> * Storage Table Data Contributor| Enable tracing data including node level outputs/trace/logs when performing inference. Currently it's not required.|

To grant permissions to the endpoint identity, there are 2 ways:

- You can leverage ARM template to grant all permissions. You can find related ARM templates [here](https://github.com/cloga/azure-quickstart-templates/tree/lochen/promptflow/quickstarts/microsoft.machinelearningservices/machine-learning-prompt-flow). 

- You can also grant all permissions in Azure portal UI by following steps.

    1. Go to the AzureML workspace overview page in [Azure portal](https://ms.portal.azure.com/#home).


    1. Select **Access control**, and select **Add role assignment**.

        ![access-control](../media/how-to-deploy-for-real-time-inference/access-control.png)

    1. Select **AzureML Data Scientist**, go to **Next**.

        > [!NOTE]
        >
        > AzureML Data Scientist is a built-in role which has permission to get workspace connections. 
        >
        > If you want to use a customized role, make sure the customized role has the permission of “Microsoft.MachineLearningServices/workspaces/connections/listsecrets/action”. Learn more about [how to create custom roles](https://learn.microsoft.com/azure/role-based-access-control/custom-roles-portal#step-3-basics).

    1. Select **Managed identity** and select members. 
       
        For **system-assigned identity**, select **Machine learning online endpoint** under **System-assigned managed identity**, and search by endpoint name.

        ![select-system-identity](../media/how-to-deploy-for-real-time-inference/select-si.png)

        For **user-assigned identity**, select **User-assigned managed identity**, and search by identity name.

        ![select-user-identity](../media/how-to-deploy-for-real-time-inference/select-ui.png)

    1. For user-assigned identity, you need to grant permissions to the workspace container registry as well. Go to the workspace container registry overview page, select **Access control**, and select **Add role assignment**, and assign **Acr pull |Pull container image** to the endpoint identity.

        ![workspace-storage-container-registry](../media/how-to-deploy-for-real-time-inference/storage-container-registry.png)    

    1. Currently the permissions on workspace default storage is not required. If you want to enable tracing data including node level outputs/trace/logs when performing inference, you can grant permissions to the workspace default storage as well. Go to the workspace default storage overview page, select **Access control**, and select **Add role assignment**, and assign *Storage Blob Data Contributor* and *Storage Table Data Contributor* to the endpoint identity respectively.
  
          
## Test the endpoint with sample data

In the endpoint detail page, switch to the **Test** tab.

If you select **Allow sharing sample input data for testing purpose only** when you deploy the endpoint, you can see the input data values are already preloaded.

If there is no sample value, you'll need to input a URL.

The **Test result** shows as following: 

![test-endpoint](../media/how-to-deploy-for-real-time-inference/test-endpoint.png)

### Test the endpoint deployed from a chat flow

For endpoints deployed from chat flow, you can test it in a immersive chat window.

![test-chat-endpoint](../media/how-to-deploy-for-real-time-inference/test-chat-endpoint.png)

The `chat_input` was set during development of the chat flow. You can input the `chat_input` message in the input box. The **Inputs** panel on the right side is for you to specify the values for other inputs besides the `chat_input`. Learn more about [how to develop a chat flow](./how-to-develop-a-chat-flow.md).

## Consume the endpoint

In the endpoint detail page, switch to the **Consume** tab. You can find the REST endpoint and key/token to consume your endpoint. There are also sample code for you to consume the endpoint in different languages.

## (Optional) View metrics using Azure Monitor
You can view various metrics (request numbers, request latency, network bytes, CPU/GPU/Disk/Memory utilization, and more) for an online endpoint and its deployments by following links from the endpoint's **Details** page in the studio. Following these links will take you to the exact metrics page in the Azure portal for the endpoint or deployment.

> [!NOTE]
> 
> If you specify user-assigned identity for your endpoint, make sure that you have assigned **Workspace metrics writer** of **Azure Machine Learning Workspace** to your user-assigned identity. Otherwise, the endpoint will not be abled to log the metrics.

![endpoint-metrics](../media/how-to-deploy-for-real-time-inference/view-metrics.png)

For more information on how to view online endpoint metrics, see [Monitor online endpoints](https://learn.microsoft.com/azure/machine-learning/how-to-monitor-online-endpoints?view=azureml-api-2#metrics).


## Clean up resources

If you aren't going use the endpoint after completing this tutorial, you should delete the endpoint.

> [!NOTE]
> The complete deletion may take approximately 20 minutes.


## Next Steps

- [Iterate and optimize your flow by tuning prompts using variants](how-to-tune-prompts-using-variants.md)
- [View costs for an Azure Machine Learning managed online endpoint](https://learn.microsoft.com/azure/machine-learning/how-to-view-online-endpoints-costs?view=azureml-api-2)
