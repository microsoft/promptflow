# Custimize environment for runtime
We have following approaches to customize environment for runtime:
- Manually customize conda packages in CI runtime
- Customize environment with docker context for runtime

Meanwhile, you can also create custom application on compute instance and managed online endpoint then use them as runtime. 
## Manually customize conda packages in CI runtime

1. Go to runtime list page find the compute instance linked with runtime.
![runtime-creation-ci-runtime-list-compute-link](../media/runtime/runtime-creation-ci-runtime-list-compute-link.png)

2. Under `applications` in the detail page of the compute instance, click `terminal`.
![runtime-creation-ci-runtime-list-compute-terminal](../media/runtime/runtime-creation-ci-runtime-list-compute-terminal.png)

3. Jump to terminal on this compute instance
![runtime-creation-ci-runtime-list-compute-jump-to-terminal](../media/runtime/runtime-creation-ci-runtime-list-compute-jump-to-terminal.png)

4. Retrieve the container name of the runtime using the command `docker ps`.
![runtime-creation-ci-runtime-list-compute-terminal-docker-ps](../media/runtime/runtime-creation-ci-runtime-list-compute-terminal-docker-ps.png)

5. Jump into the container using the command `docker exec -it <container_id/container_name> /bin/bash`
![runtime-creation-ci-runtime-list-compute-terminal-docker-exec](../media/runtime/runtime-creation-ci-runtime-list-compute-terminal-docker-exec.png)

6. You can now install packages using `conda install` or `pip install` in this conda environment.

**Note:** Any package installed in this way may be lost after a compute instance restart. If you want to keep these packages, please follow the instructions in the section titled [Customize Environment with Docker Context for Runtime](#customize-environment-with-docker-context-for-runtime).

## Customize environment with docker context for runtime

This section assumes you have knowledge of [Docker](https://www.docker.com/) and [Azure Machine Learning environments](https://learn.microsoft.com/en-us/azure/machine-learning/concept-environments?view=azureml-api-2).


### Step-1: Prepare the docker context

#### 1.1 Create `image_build` folder

In your local environment, create a folder contains following files, the folder structure should look like this:

```
|--image_build
|  |--requirements.txt
|  |--Dockerfile
|  |--environment-build.yaml
|  |--environment.yaml
```

#### 1.2 Define your required packages in `requirements.txt`

**Optional**: Add packages in private pypi repository.

Using the following command to download your packages to local: `pip wheel <package_name> --index-url=<private pypi> --wheel-dir <local path to save packages>`

Open the `requirements.txt` file and add your extra packages and specific version in it.  For example:

```
###### Requirements with Version Specifiers ######
langchain == 0.0.149        # Version Matching. Must be version 0.6.1
keyring >= 4.1.1            # Minimum version 4.1.1
coverage != 3.5             # Version Exclusion. Anything except version 3.5
Mopidy-Dirble ~= 1.1        # Compatible release. Same as >= 1.1, == 1.*
```

You can obtain the path of local packages using `ls > requirements.txt`.

#### 1.3 Define the `Dockerfile`

Create a `Dockerfile` and add the following content, then save the file:

```
FROM <Base_image>
COPY ./* ./
RUN pip install -r requirements.txt
```

Note: this docker image should be built from prompt flow base image that is `mcr.microsoft.com/azureml/promptflow/promptflow-runtime:<newest_version>`. You can find the latest version of the base image on [this page](https://mcr.microsoft.com/v2/azureml/promptflow/promptflow-runtime/tags/list).

### Step2: Use AzureML environment to build image

#### 2.1 Define your environment in `environment_build.yaml`

In your local compute, you can use the CLI (v2) to create a customized environments based on your docker image.

Note:

- Make sure to meet the [prerequisites](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-environments-v2?view=azureml-api-2&tabs=cli#prerequisites) for creating environment.
- Ensure  you have [connected to your workspace](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-environments-v2?view=azureml-api-2&tabs=cli#prerequisites).

```shell
az login(optional)
az account set --subscription <subscription ID>
az configure --defaults workspace=<Azure Machine Learning workspace name> group=<resource group>
```

Open the `environment_build.yaml` file and add the following content. Replace the <environment_name_docker_build> placeholder with your desired environment name.

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/environment.schema.json
name: <environment_name_docker_build>
build:
  path: .
```

#### 2.2 Run CLI command to create an environment

```bash
cd image_build
az login(optional)
az ml environment create -f environment_build.yaml
```

**Note:** Building the image may take several minutes.

#### 2.3 Locate the image in ACR

Go to the environment page to find the built image in your workspace ACR.
![runtime-update-env-custom-environment-list](../media/runtime/runtime-update-env-custom-environment-list.png)

Find the image in ACR.
![runtime-update-env-custom-environment-acr](../media/runtime/runtime-update-env-custom-environment-acr.png)

**Note**: Please make sure the `Environment image build status` is `Succeeded`  before using it in the next step.

### Step3: Create a custom AzureML environment for runtime 

#### 3.1 Create a custom AzureML environment for runtime in docker hub - compute instance runtime
**Note**: Compute instance only support image in public docker hub or MCR, so you need push the image to docker hub or MCR, then use them to create custom environemnt. 

```shell
docker login <the_acr_you_build_image_in_previous_step>
docker pull <image_build_in_acr>
docker login <your_public_docker_hub>
docker tag <image_build_in_acr> <image_in_your_public_docker_hub>
docker push <image_in_your_public_docker_hub>
```

Open the `environment.yaml` file and add the following content. Replace the `<environment_name>` placeholder with your desired environment name and change `<image_build_in_acr>` to the ACR image found in the previous step.

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/environment.schema.json
name: <environment_name>
image: <image_in_your_public_docker_hub>
inference_config:
  liveness_route:
    port: 8080
    path: /health
  readiness_route:
    port: 8080
    path: /health
  scoring_route:
    port: 8080
    path: /score
```

Using following CLI command to create the environment:

```bash
cd image_build # optional if you already in this folder
az login(optional)
az ml environment create -f environment.yaml
```

#### 3.2 Create a custom AzureML environment for runtime in ACR - Managed online deployment runtime

Open the `environment.yaml` file and add the following content. Replace the `<environment_name>` placeholder with your desired environment name and change `<image_build_in_acr>` to the ACR image found in the step 2.3.

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/environment.schema.json
name: <environment_name>
image: <image_build_in_acr>
inference_config:
  liveness_route:
    port: 8080
    path: /health
  readiness_route:
    port: 8080
    path: /health
  scoring_route:
    port: 8080
    path: /score
```

Using following CLI command to create the environment:

```bash
cd image_build # optional if you already in this folder
az login(optional)
az ml environment create -f environment.yaml
```

Go to your workspace UI page, go to the `environment` page,  and locate the custom environment you created. You can now use it to create a runtime in your prompt flow. Learn more:

- [Create compute instance runtime in UI](how-to-create-manage-runtime.md#create-compute-instance-runtime-in-ui)
- [Create managed online endpoint runtime in UI](how-to-create-manage-runtime.md#create-managed-online-endpoint-runtime-in-ui)

Refer to this documentation to learn more about environment CLI: <https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-environments-v2?view=azureml-api-2&tabs=cli#manage-environments>


## Create custom appliction on compute instance which can be used as prompt flow runtime
A prompt flow runtime is a custom application that runs on a compute instance. You can create a custom application on a compute instance and then use it as a prompt flow runtime. To create a custom application for this purpose, you need to specify the following properties:

|UI|SDK|Note|
|--|--|--|
|Docker image|ImageSettings.reference|Image used to build this custom application|
|Target port|EndpointsSettings.target|Port where you want to access the application, the port inside the container|
|published port|EndpointsSettings.published|Port where your application is running in the image, the publicly exposed port|

### Create custom application as prompt flow runtime via SDK v2
```python
# import required libraries
import os
from azure.ai.ml import MLClient
from azure.ai.ml.entities import WorkspaceConnection
# Import required libraries
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential

try:
    credential = DefaultAzureCredential()
    # Check if given credential can get token successfully.
    credential.get_token("https://management.azure.com/.default")
except Exception as ex:
    # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
    credential = InteractiveBrowserCredential()

from azure.ai.ml.entities import ComputeInstance 
from azure.ai.ml.entities import CustomApplications, ImageSettings, EndpointsSettings, VolumeSettings 

ml_client = MLClient.from_config(credential=credential)

image = ImageSettings(reference='mcr.microsoft.com/azureml/promptflow/promptflow-runtime:<newest_version>') 

endpoints = [EndpointsSettings(published=8081, target=8080)]

app = CustomApplications(name='promptflow-runtime',endpoints=endpoints,bind_mounts=[],image=image,environment_variables={}) 

ci_basic_name = "<compute_instance_name>"

ci_basic = ComputeInstance(name=ci_basic_name, size="<instance_type>",custom_applications=[app]) 

ml_client.begin_create_or_update(ci_basic)
```
Please change `newest_version`, `compute_instance_name` and `instance_type` to your own value.

### Create custom application as prompt flow runtime via ARM template
You can use this ARM template to create compute instance with custom application.

 [![Deploy To Azure](https://raw.githubusercontent.com/Azure/azure-quickstart-templates/master/1-CONTRIBUTION-GUIDE/images/deploytoazure.svg?sanitize=true)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fcloga%2Fazure-quickstart-templates%2Flochen%2Fpromptflow%2Fquickstarts%2Fmicrosoft.machinelearningservices%2Fmachine-learning-prompt-flow%2Fcreate-compute-instance-with-custom-application%2Fazuredeploy.json)

Learn more about [ARM template for custom application as prompt flow runtime on compute instance](https://github.com/cloga/azure-quickstart-templates/tree/lochen/promptflow/quickstarts/microsoft.machinelearningservices/machine-learning-prompt-flow/create-compute-instance-with-custom-application)

### Create custom application as prompt flow runtime via Compute instance UI
Follow [this document to add custom application](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-create-manage-compute-instance?view=azureml-api-2&tabs=python#setup-other-custom-applications)

![runtime-creation-add-custom-application-ui](../media/runtime/runtime-creation-add-custom-application-ui.png)


## Create managed online deployment which can be used as prompt flow runtime

### Create managed online deployment which can be used as prompt flow runtime via CLI v2

Learn more about [deploy and score a machine learning model by using an online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2&tabs=azure-cli)

#### Create managed online  endpoint

To define a managed online endpoint, you can use the following yaml template. Make sure to replace the `ENDPOINT_NAME` with the desired name for your endpoint.

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineEndpoint.schema.json
name: <ENDPOINT_NAME>
description: this is a sample promptflow endpoint
auth_mode: key
```

Use following CLI command `az ml online-endpoint create -f <yaml_file> -g <resource_group> -w <workspace_name>` to create managed online endpoint. Learn more: [Deploy and score a machine learning model by using an online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2&tabs=azure-cli)

#### Create promptflow runtime image config file

To configure your promptflow runtime, please place the following config file in your model folder. This config file will provide the necessary information for the runtime to work properly.

For the `mt_service_endpoint` parameter, please follow this format: `https://<region>.api.azureml.ms`. For example, if your region is eastus, then your service endpoint should be `https://eastus.api.azureml.ms`

```yaml
storage:
  storage_account: <WORKSPACE_LINKED_STORAGE>
deployment:
  subscription_id: <SUB_ID>
  resource_group: <RG_NAME>
  workspace_name: <WORKSPACE_NAME>
  endpoint_name: <ENDPOINT_NAME>
  deployment_name: blue
  mt_service_endpoint: <PROMPT_FLOW_SERVICE_ENDPOINT>
```

#### Create managed online online endpoint

You need to replace the following placeholders with your own values:
 - `ENDPOINT_NAME`: the name of the endpoint you created in the previous step
 - `PRT_CONFIG_FILE`: the name of the config file that contains the port and runtime settings
 - `IMAGE_NAME` to name of your own image, for example: `mcr.microsoft.com/azureml/promptflow/promptflow-runtime:<newest_version>`, you can also follow [this section](#customize-environment-with-docker-context-for-runtime) to create your own environment.
 

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
name: blue
endpoint_name: <ENDPOINT_NAME>
type: managed
model:
  path: ./
  type: custom_model
instance_count: 1
# 4core, 32GB
instance_type: Standard_E4s_v3
request_settings:
  max_concurrent_requests_per_instance: 10
  request_timeout_ms: 90000
environment_variables:
  PRT_CONFIG_FILE: <PRT_CONFIG_FILE>
environment:
  name: promptflow-runtime
  image: <IMAGE_NAME>
  inference_config:
    liveness_route:
      port: 8080
      path: /health
    readiness_route:
      port: 8080
      path: /health
    scoring_route:
      port: 8080
      path: /score

```

Use following CLI command `az ml online-deployment create -f <yaml_file> -g <resource_group> -w <workspace_name>` to create managed online deployment which can used as prompt flow runtime.

Follow [Create managed online endpoint runtime in UI](how-to-create-manage-runtime.md#create-managed-online-endpoint-runtime-in-ui) to select this deployment as prompt flow runtime.