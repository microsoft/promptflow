# Set up e2e LLMOps with Promptflow and GitHub (preview)

Azure Machine Learning allows you to integrate with [GitHub Actions](https://docs.github.com/actions) to automate the machine learning lifecycle. Some of the operations you can automate are:

* Running Prompt flow after a Pull Request
* Running Prompt flow evaluation to ensure results are high quality 
* Registering of prompt flow models
* Deployment of prompt flow models

In this article, you learn about using Azure Machine Learning to set up an end-to-end LLMOps pipeline that runs a web classification flow that classifies a website based on a given URL. The flow is made up of multiple LLM calls and components, each serving  different functions. All the LLMs used are managed and store in your Azure Machine Learning workspace in your Promptflow connections

> [!TIP]
> We recommend you understand how we integrate [LLMOps with Promptflow](//) 

## Prerequisites

- An Azure subscription. If you don't have an Azure subscription, create a free account before you begin. Try the [free or paid version of Machine Learning](https://azure.microsoft.com/free/).
- A Machine Learning workspace.
- Git running on your local machine.
- GitHub as the source control repository

> [!NOTE]
>
>Git version 2.27 or newer is required. For more information on installing the Git command, see https://git-scm.com/downloads and select your operating system

> [!IMPORTANT]
>The CLI commands in this article were tested using Bash. If you use a different shell, you may encounter errors.

## Set up authentication with Azure and GitHub

Before you can set up an Promptflow project with Machine Learning, you need to set up authentication for Azure GitHub.

### Create service principal
   Create one Prod service principal for this demo. You can add more depending on how many environments, you want to work on (Dev or Prod or Both). Service principals can be created using one of the following methods:

# [Create from Azure Cloud Shell](#tab/azure-shell)

1. Launch the [Azure Cloud Shell](https://shell.azure.com).

    > [!TIP]
    > The first time you've launched the Cloud Shell, you'll be prompted to create a storage account for the Cloud Shell.

1. If prompted, choose **Bash** as the environment used in the Cloud Shell. You can also change environments in the drop-down on the top navigation bar

    ![Screenshot of the cloud shell environment dropdown.](../media/e2e-llmops/PS_CLI1_1.png)

1. Copy the following bash commands to your computer and update the **projectName**, **subscriptionId**, and **environment** variables with the values for your project. This command will also grant the **Contributor** role to the service principal in the subscription provided. This is required for GitHub Actions to properly use resources in that subscription. 

    ``` bash
    projectName="<your project name>"
    roleName="Contributor"
    subscriptionId="<subscription Id>"
    environment="<Prod>" #First letter should be capitalized
    servicePrincipalName="Azure-ARM-${environment}-${projectName}"
    # Verify the ID of the active subscription
    echo "Using subscription ID $subscriptionID"
    echo "Creating SP for RBAC with name $servicePrincipalName, with role $roleName and in scopes     /subscriptions/$subscriptionId"
    az ad sp create-for-rbac --name $servicePrincipalName --role $roleName --scopes /subscriptions/$subscriptionId --sdk-auth 
    echo "Please ensure that the information created here is properly save for future use."
    ```

1. Copy your edited commands into the Azure Shell and run them (**Ctrl** + **Shift** + **v**).

1. After running these commands, you'll be presented with information related to the service principal. Save this information to a safe location, you'll use it later in the demo to configure GitHub.

    ```json

      {
      "clientId": "<service principal client id>",  
      "clientSecret": "<service principal client secret>",
      "subscriptionId": "<Azure subscription id>",  
      "tenantId": "<Azure tenant id>",
      "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
      "resourceManagerEndpointUrl": "https://management.azure.com/", 
      "activeDirectoryGraphResourceId": "https://graph.windows.net/", 
      "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
      "galleryEndpointUrl": "https://gallery.azure.com/",
      "managementEndpointUrl": "https://management.core.windows.net/" 
      }
    ```

1. Copy all of this output, braces included. Save this information to a safe location, it will be use later in the demo to configure GitHub Repo.

1. Close the Cloud Shell once the service principals are created. 

## Clone Example Repo
1. Fork example repo. [LLMOps Repo](https://github.com/AbeOmor/llmops-pipeline/fork)

1. Clone repo to your local machine
```
 git clone https://github.com/<user-name>/llmops-pipeline
```
## Add secret to GitHub Repo

1. From your GitHub project, select **Settings**:

    ![Screenshot of GitHub Settings.](../media/e2e-llmops/github-settings.png)

1. Then select **Secrets**, then **Actions**:

    ![Screenshot of GitHub Secrets.](../media/e2e-llmops/github-secrets.png)

1. Select **New repository secret**. Name this secret **AZURE_CREDENTIALS** and paste the service principal output as the content of the secret.  Select **Add secret**.

    ![Screenshot of GitHub Secrets String 1.](../media/e2e-llmops/github-secrets-string.png)

1. Add each of the following additional GitHub secrets using the corresponding values from the service principal output as the content of the secret:  
    - **ARM_CLIENT_ID**  
    - **ARM_CLIENT_SECRET**  
    - **ARM_SUBSCRIPTION_ID**  
    - **ARM_TENANT_ID**  

    ![Screenshot of GitHub Secrets String 2.](../media/e2e-llmops/github-secrets-string-2.png)


> [!NOTE]
> This finishes the prerequisite section and the deployment of the solution accelerator can happen accordingly.

## Setup connections for Prompt flow 

Connection helps securely store and manage secret keys or other sensitive credentials required for interacting with LLM and other external tools for example Azure Content Safety.

In this guide, we will use flow `web-classification` which uses connection `azure_open_ai_connection` inside, we need to set up the connection if we haven’t added it before.

Please go to workspace portal, click `Prompt flow` -> `Connections` -> `Create`, then follow the instruction to create your own connections. Learn more on [connections](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/concept-connections?view=azureml-api-2).

## Setup variables with for Prompt flow and GitHub Actions 

### Update workflow to connect to your Azure Machine Learning workspace
1. Update `run-eval-pf-pipeline.yml` and `deploy-pf-online-endpoint-pipeline.yml` to connect to your Azure Machine Learning workspace
You'll need to update the CLI setup file variables to match your workspace. 

1. In your cloned repository, go to `.github/workflow/`. 
1. Edit `env` section in the `run-eval-pf-pipeline.yml` and `deploy-pf-online-endpoint-pipeline.yml` and update these variables in the file. 
   
    |Variable  | Description  |
    |---------|---------|
    |GROUP     |      Name of resource group    |
    |SUBSCRIPTION     |    Subscription of your workspace    |
    |WORKSPACE     |     Name of Azure Machine Learning workspace     | 

### Update run.yml with your connections and runtime

You'll use a `run.yml` file to deploy your Azure Machine Learning pipeline. This is a flow run definition. You only need to make this update if you're using a name other than `pf-runtime` for your [prompt flow runtime](https://learn.microsoft.com/azure/machine-learning/prompt-flow/how-to-create-manage-runtime). You will also need to update all the `connections` to match the connections in your Azure Machine Learning workspace and `deployment_name` to match the name of your GPT 3.5 Turbo deployment associate with that connection.

1. In your cloned repository, go to `web-classification/run.yml`. 
1. Each time you see `runtime: abe`, update the value of `pf-runtime` with your runtime name.
1. Each time you see `connection: Default_AzureOpenAI`, update the value of `Default_AzureOpenAI`  to match the connection name in your Azure Machine Learning workspace.
1. Each time you see `deployment_name: gpt-35-turbo-0301`, update the value of `gpt-35-turbo-0301` with the name of your GPT 3.5 Turbo deployment associate with that connection.

## Sample Prompt Run, Evaluation and Deployment Scenario

This is a flow demonstrating multi-class classification with LLM. Given an url, it will classify the url into one web category with just a few shots, simple summarization and classification prompts.

In this flow, you will learn
This training pipeline contains the following steps:

**Run Prompts in Flow**
- Compose a classification flow with LLM.
- Feed few shots to LLM classifier.
- Upload prompt test dataset,
- Bulk run prompt flow based on dataset.

**Evaluate Results**
- Upload ground test dataset
- Evaluation of the bulk run result and new uploaded ground test dataset

**Register Prompt Flow LLM App**
- Check in logic, Customer defined logic (accuracy rate, if >=90% you can deploy)

**Deploy and Test LLM App**
- Deploy the PF as a model to production
- Test the model/promptflow realtime endpoint.

## Run and Evaluate Prompt Flow in AzureML with GitHub Actions
Using a [GitHub Action workflow](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-github-actions-machine-learning?view=azureml-api-2&tabs=userlevel#step-5-run-your-github-actions-workflow) we will trigger actions to run a Prompt Flow job in Azure Machine learning. 

This pipeline will start the promptflow run and evaluate the results. When the job is complete, the prompt flpw model will be registered in the Azure Machine Learning workspace and be available for deployment.

1. In your GitHub project repository, select **Actions**  
 
     ![Screenshot of GitHub actions page.](../media/e2e-llmops/github-actions.png)
      
1. Select the `run-eval-pf-pipeline.yml` from the workflows listed on the left and the click **Run Workflow** to execute the Prompt flow run and evaluate workflow. This will take several minutes to run. 

     ![Screenshot of Pipeline Run in GitHub.](../media/e2e-llmops/github-training-pipeline.png)

1. The workflow will only register the model for deployment, if the accuracy of the classification is greater than 60%. You can adjust the accuracy thresold in the `run-eval-pf-pipeline.yml` file in the `jobMetricAssert` section of the workflow file. The section should look like:

    ```yaml
    id: jobMetricAssert
    run: |
        export ASSERT=$(python promptflow/llmops-helper/assert.py result.json 0.6)
    ```
    You can update the current `0.6` number to fit your preferred threshold.

1. Once completed, a successful run and all test were passed, it will register the Prompt Flow model in the Machine Learning workspace. 
  
     ![Screenshot of Training Step in GitHub Actions.](../media/e2e-llmops/github-training-step.png)

> [!NOTE] 
> If you want to check the output of each individual step, for example to view output of a failed run, click a job output, and then click each step in the job to view any output of that step. 

With the Prompt flow model registered in the Machine learning workspace, you are ready to deploy the model for scoring.

## Deploy Prompt Flow in AzureML with GitHub Actions

This scenario includes prebuilt workflows for two approaches to deploying a trained model, batch scoring or a deploying a model to an endpoint for real-time scoring. You may run either or both of these workflows to test the performance of the model in your Azure Machine Learning workspace.

### Online Endpoint  
      
1. In your GitHub project repository , select **Actions**  
 
      ![Screenshot of GitHub actions page.](../media/e2e-llmops/github-actions.png)


1. Select the **deploy-pf-online-endpoint-pipeline** from the workflows listed on the left and click **Run workflow** to execute the online endpoint deployment pipeline workflow. The steps in this pipeline will create an online endpoint in your Machine Learning workspace, create a deployment of your model to this endpoint, then allocate traffic to the endpoint.

     ![Screenshot of GitHub action for online endpoint.](../media/e2e-llmops/github-online-endpoint.png)
   
1. Once completed, you will find the online endpoint deployed in the Azure Machine Learning workspace and available for testing.

     ![Screenshot of Machine Learning taxi online endpoint.](../media/e2e-llmops/azure-ml-web-class-online-endpoint.png)


1. To test this deployment, go to the **Endpoints** tab in your Machine Learning workspace, select the endpoint and click the **Test** Tab. You can use the sample input data located in the cloned repo at `/deployment/sample-request.json` to test the endpoint.

     ![Screenshot of Machine Learning taxi Online endpoint test.](../media/e2e-llmops/azure-ml-online-endpoint-test.png)


## Moving to production

This example scenario can be run and deployed both for Dev and Prod branches and environments. When you are satisfied with the performance of the prompt evaluation pipeline, Prompt Flow model, and deployment in Testing, Dev pipelines and models can be replicated and deployed in the Production environment.

The sample Prompt flow run & evaluation and GitHub workflows can be used as a starting point to adapt your own prompt engineering code and data.

## Clean up resources

1. If you're not going to continue to use your pipeline, delete your GitHub project. 
1. In Azure portal, delete your resource group and Machine Learning instance.

## Next steps

* [Install and set up Python SDK v2](https://aka.ms/sdk-v2-install)
* [Install and set up Python CLI v2](how-to-configure-cli.md)
* [Prompt Flow Docs]() 
* [Gen AI Docs]() 