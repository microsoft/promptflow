# Create and manage runtimes

Prompt flow's runtime provides the computing resources required for the application to run, including a Docker image that contains all necessary dependency packages. This reliable and scalable runtime environment enables prompt flow to efficiently execute its tasks and functions, ensuring a seamless user experience for users.

## Runtime type

You can choose between two types of runtimes for prompt flow: [managed online endpoint/deployment](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online) and [compute instance (CI)](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-instance). Here are some differences between them to help you decide which one suits your needs.

|Runtime type|Managed online deployment runtime|Compute instance runtime|
|------------|-----------|----------|
|Team shared |Y|N|
|User isolation|N|Y|
|OBO/identity support|N|Y|
|Easily manually customization of environment|N|Y|
|Multiple runtimes on single resource|N|Y|

If you are new to prompt flow, we recommend you to start with compute instance runtime first.

## Permissions/roles need to use runtime
You need to assign enough permission to use runtime in prompt flow. To assign a role you need have `owner` or have `Microsoft.Authorization/roleAssignments/write` permission on resource.
- To create runtime, you need have `AzureML Data Scientist` role of the workspace. [Learn more](#prerequisite)
- To use a runtime in flow authoring, you or identity associate with managed online endpoint need have `AzureML Data Scientist` role of workspace, `Storage Blob Data Contributor` and `Storage Table Data Contributor` role of workspace default storage. [Learn more](#grant-sufficient-permissions-to-use-the-runtime).

## Create runtime in UI

### Prerequisite

- Please make sure your workspace linked with ACR, you can link an existing ACR when you are creating a new workspace, or you can trigger environment build which may auto link ACR to AzureML workspace. [Learn more how to trigger environment build in workspace](#potential-root-cause-and-solution)
- You need `AzureML Data Scientist` role of the workspace to create a runtime.

### Create compute instance runtime in UI

If your didn't have compute instance, please follow this doc to create a new one: [Create and manage an Azure Machine Learning compute instance](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-create-manage-compute-instance)

#### 1. Select add compute instance runtime in runtime list page
![runtime-creation-runtime-list-add](../media/runtime/runtime-creation-runtime-list-add.png)

#### 2. Select compute instance you want to use as runtime.
![runtime-creation-ci-runtime-select-ci](../media/runtime/runtime-creation-ci-runtime-select-ci.png)

Because compute instances are isolated by user, you can only see your own compute instances or the ones assigned to you. More information: [Create and manage an Azure Machine Learning compute instance](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-create-manage-compute-instance).

#### 3. Select create new custom application or existing custom application as runtime.

##### 3.1 Select create new custom application as runtime.
![runtime-creation-ci-runtime-select-custom-application](../media/runtime/runtime-creation-ci-runtime-select-custom-application.png)

This is recommended for most users of prompt flow. The prompt flow system will create a new custom application on a compute instance as a runtime.

  - To choose the default environment, select this option. This is the recommended choice for new users of prompt flow.

![runtime-creation-runtime-list-add-default-env](../media/runtime/runtime-creation-runtime-list-add-default-env.png)

  - If you want to install additional packages in your project, you should create a custom environment. [This section](how-to-customize-environment-runtime.md#customize-environment-with-docker-context-for-runtime) will guide you through the steps to build your own custom environment.

![runtime-creation-runtime-list-add-custom-env](../media/runtime/runtime-creation-runtime-list-add-custom-env.png)

**Note**: 
  - We are going to perform an automatic restart of your compute instance. Please ensure that you do not have any tasks or jobs running on it, as they may be affected by the restart. 
  - To build your custom environment, please use an image from public docker hub. We do not support custom environments built with images from ACR at this time.

##### 3.2 To use an existing custom application as a runtime, choose the option "existing". 

This option is available if you have previously created a custom application on a compute instance. For more information on how to create and use a custom application as a runtime, learn more about [how to create custom application as runtime](how-to-customize-environment-runtime.md#create-custom-appliction-on-compute-instance-which-can-be-used-as-prompt-flow-runtime).

![runtime-creation-ci-existing-custom-application-ui](../media/runtime/runtime-creation-ci-existing-custom-application-ui.png)

### Create managed online endpoint runtime in UI

#### 1. Specify the runtime name.
![runtime-creation-mir-runtime-runtime-name](../media/runtime/runtime-creation-mir-runtime-runtime-name.png)

#### 2. Select existing or create a new deployment as runtime
##### 2.1 Select create new deployment as runtime.
![runtime-creation-mir-runtime-deployment-new](../media/runtime/runtime-creation-mir-runtime-deployment-new.png)

There are two options for deployment as runtime: `new` and `existing`. If you choose `new`, we will create a new deployment for you. If you choose `existing`, you need to provide the name of an existing deployment as runtime.

If you are new to prompt flow, select `new` and we will create a new deployment for you.

  - Select identity type of endpoint.
![runtime-creation-mir-runtime-identity](../media/runtime/runtime-creation-mir-runtime-identity.png)

You need [assign sufficient permission](#grant-sufficient-permissions-to-use-the-runtime) to system assigned identity or user assigned identity.

Learn more [Access Azure resources from an online endpoint with a managed identity](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-access-resources-from-endpoints-managed-identities?view=azureml-api-2&tabs=system-identity-cli)

  - Select environment used for this runtime.
![runtime-creation-mir-runtime-env](../media/runtime/runtime-creation-mir-runtime-env.png)

Please follow [this part](how-to-customize-environment-runtime.md#customize-environment-with-docker-context-for-runtime) to build your custom environment.

  - Choose the appropriate SKU and instance count.

    > [!NOTE]
    >
    > For **Virtual machine**, since the prompt flow runtime is memory-bound, it’s better to select a virtual machine SKU with more than 8GB of memory.  For the list of supported sizes, see [Managed online endpoints SKU list](https://learn.microsoft.com/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list?view=azureml-api-2).

    ![runtime-creation-mir-runtime-compute](../media/runtime/runtime-creation-mir-runtime-compute.png)

**Note**: Creating a managend online deployment runtime using new deployment may take several minutes.

#### 2.2 Select existing deploymennt as runtime.

  - To use an existing managed online deployment as a runtime, you can choose it from the available options. Each runtime corresponds to one managed online deployment.
![runtime-creation-mir-runtime-existing-deployment](../media/runtime/runtime-creation-mir-runtime-existing-deployment.png)

  - You can select from existing endpoint and existing deployment as runtime.
![runtime-creation-mir-runtime-existing-deployment-select-endpoint](../media/runtime/runtime-creation-mir-runtime-existing-deployment-select-endpoint.png)

  - We will verify that this deployment meets the runtime requirements.
![runtime-creation-mir-runtime-existing-deployment-select-deployment](../media/runtime/runtime-creation-mir-runtime-existing-deployment-select-deployment.png)


Learn more about [how to create managed online deployment which can be used as prompt flow runtime](how-to-customize-environment-runtime.md#create-managed-online-deployment-which-can-be-used-as-prompt-flow-runtime).

## Grant sufficient permissions to use the Runtime

After creating the runtime, you need to grant the necessary permissions to use it.

### Permissions required to assign roles

To assign role you need have `owner` or have `Microsoft.Authorization/roleAssignments/write` permission on resource.

### Assign built-in roles

To use runtime, assigning the following roles to user (if using Compute instance as runtime) or endpoint (if using MIR as runtime).
|Resource|Role|Why need this|
|--------|----|-------------|
|Workspace|AzureML Data Scientist|Used to write to runhistory, log metrics|
|Workspace default ACR|AcrPull|Pull image from ACR|
|Workspace default storage|Storage Blob Data Contributor|Write intermediate data and tracing data|
|Workspace default storage|Storage Table Data Contributor|Write intermediate data and tracing data|

You can use this ARM template to assign these roles to your user or endpoint.

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fcloga%2Fazure-quickstart-templates%2Flochen%2Fpromptflow%2Fquickstarts%2Fmicrosoft.machinelearningservices%2Fmachine-learning-prompt-flow%2Fassign-built-in-roles%2Fazuredeploy.json)

To find the minimal permissions required, and use an ARM template to create a custom role and assign relevant permissions, visit: [Permissions/roles need to use runtime](./how-to-create-manage-runtime.md#permissionsroles-need-to-use-runtime)

You can also assign these permissions manually through the UI.

- Click top-right conner  to access the AzureML workspace detail page.
![mir-without-acr-runtime-workspace-top-right](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-workspace-top-right.png)

- Locate the **default storage account** and **ACR** on the AzureML workspace detail page.
![runtime-permission-workspace-detail-storage-acr](../media/runtime/runtime-permission-workspace-detail-storage-acr.png)

- Navigate to `access control` to grant the relevant roles to the workspace, storage account, and ACR. 
![runtime-permission-workspace-access-control](../media/runtime/runtime-permission-workspace-access-control.png)

- Select user if you are using compute instance
![runtime-permission-rbac-user](../media/runtime/runtime-permission-rbac-user.png)

- Alternatively, choose the managed identity and machine learning online endpoint for the MIR runtime.
![runtime-permission-rbac-msi](../media/runtime/runtime-permission-rbac-msi.png)

**Note**: This operation may take several minutes to take effect.

**Learn more:**

- <https://learn.microsoft.com/en-us/azure/machine-learning/how-to-assign-roles?view=azureml-api-2&tabs=labeler>

- <https://learn.microsoft.com/en-us/azure/storage/blobs/assign-azure-role-data-access?tabs=portal>

- <https://learn.microsoft.com/en-us/azure/container-registry/container-registry-roles?tabs=azure-cli>

## Using runtime in prompt flow authoring

When you authoring your prompt flow, you can select and change the runtime from left top conner of the flow page.
![runtime-authoring-dropdown](../media/runtime/runtime-authoring-dropdown.png)

When performing a bulk test, you can use the original runtime in the flow or change to a more powerful runtime.
![runtime-authoring-bulktest](../media/runtime/runtime-authoring-bulktest.png)

## Update runtime from UI
We regularly update our base image (`mcr.microsoft.com/azureml/promptflow/promptflow-runtime`) to include the latest features and bug fixes. We recommend that you update your runtime to the latest version if possible. You can find the latest version of the base image on [this page](https://mcr.microsoft.com/v2/azureml/promptflow/promptflow-runtime/tags/list).

Every time you open the runtime detail page, we will check whether there are new versions of the runtime. If there are new versions available, you will see a notification at the top of the page. You can also manually check the latest version by clicking the **check version** button.

![runtime-update-notification](../media/runtime/runtime-update-env-notification.png)

Please try to keep your runtime up to date to get the best experience and performance. 

Go to runtime detail page and click update button at the top. You can change new environment to update. If you select **use default environment** to update, system will attempt to update your runtime to the latest version.
![runtime-update-env](../media/runtime/runtime-update-env.png)

If you used a custom environment, you need to rebuild it using latest prompt flow image first and then update your runtime with the new custom environment.

## Troubleshooting guide for runtime

### Common issues

#### Failed to perform workspace run operations due to invalid authentication

![mir-without-ds-permission](../media/runtime/trouble-shooting-guide/mir-without-ds-permission.png)
This means the identity of the managed endpoint doesn't have enough permissions. Please follow [this part](#grant-sufficient-permissions-to-use-the-runtime) to grant sufficient permissions to the identity or user.

If you just assigned the permissions, it will take a few minutes to take effect.

#### My runtime is failed with a system error **runtime not ready** when using a custom environment

![ci-failed-runtime-not-ready](../media/runtime/trouble-shooting-guide/ci-failed-runtime-not-ready.png)
First, go to the Compute Instance terminal and run `docker ps` to find the root cause. You can follow the steps in the [Manually customize conda packages in CI runtime](how-to-customize-environment-runtime.md#manually-customize-conda-packages-in-ci-runtime) section.

Use  `docker images`  to check if the image was pulled successfully. If your image was pulled successfully, check if the Docker container is running. If it's already running, locate this runtime, which will attempt to restart the runtime and compute instance.

#### Run failed due to "No module named XXX"
This type error usually related to runtime lack required packages. If you are using default environment, please make sure image of your runtime is using the latest version, learn more: [runtime update](#update-runtime-from-ui), if you are using custom image and you are using conda environment, please make sure you have installed all required packages in your conda environment, learn more: [customize prompt flow environment](how-to-customize-environment-runtime.md#customize-environment-with-docker-context-for-runtime).


### Compute instance runtime related

#### How to find the compute instance runtime log for further investigation?

Please go to the compute instance terminal and run  `docker logs -<runtime_container_name>`


#### User does not have access to this compute instance. Please check if this compute instance is assigned to you and you have access to the workspace. Additionally, verify that you are on the correct network to access this compute instance.

![ci-flow-clone-others](../media/runtime/trouble-shooting-guide/ci-flow-clone-others.png)

This because your are cloning a flow from others which is using compute instance as runtime. As compute instance runtime is user isolated, you need to create you own compute instance runtime or select a managed online deployment/endpoint runtime which can be shared with others.

#### Compute instance behind vnet
This is known limitation, currently compute instance runtime didn't support vent.

### Managed endpoint runtime related

#### Managed Endpoint failed with an internal server error. Endpoint creation was successful, but failed to create deployment for the newly created workspace.

- Runtime status shows as failed with an internal server error.
![mir-without-acr-runtime-detail-error](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-detail-error.png)

- Check the related endpoint.
![mir-without-acr-runtime-detail-endpoint](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-detail-endpoint.png)

- Endpoint was created successfully, but there are no deployments created.
![mir-without-acr-runtime-endpoint-detail](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-endpoint-detail.png)

##### Potential root cause and solution

The issue may occur when you create a managed endpoint using a system-assigned identity. The system tries to grant ACR pull permission to this identity, but for a newly created workspace, please go to the workspace detail page in Azure to check whether the workspace has a linked ACR.

![mir-without-acr-runtime-workspace-top-right](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-workspace-top-right.png)

![mir-without-acr-runtime-workspace-non-acr](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-workspace-non-acr.png)

If there is no ACR, you can create a new custom environment from curated environments on the environment page.

![mir-without-acr-runtime-acr-creation](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-acr-creation.png)

After creating a new custom environment, a linked ACR will be automatically created for the workspace. You can return to the workspace detail page in Azure to confirm.

![mir-without-acr-runtime-workspace-with-acr](../media/runtime/trouble-shooting-guide/mir-without-acr-runtime-workspace-with-acr.png)

- Please delete the failed managed endpoint runtime and create a new one to test.

#### We are unable to connect to this deployment as runtime. Please make sure this deployment is ready to use.

![mir-existing-unable-connected](../media/runtime/trouble-shooting-guide/mir-existing-unable-connected.png)

If you encounter with this issue, please check the deployment status and make sure it is build on top of runtime base image. 