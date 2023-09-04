# Deploy to Azure App Service

[Azure App Service](https://learn.microsoft.com/azure/app-service/) is an HTTP-based service for hosting web applications, REST APIs, and mobile back ends.
The scripts (`deploy.sh` for bash and `deploy.ps1` for powershell) under [this folder](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/flow-deploy/azure-app-service) are here to help deploy the docker image to Azure App Service.

This example demos how to deploy [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/) deploy a flow using Azure App Service.

## Build a flow as docker format app

Use the command below to build a flow as docker format app:

```bash
pf flow build --source ../../flows/standard/web-classification --output build --format docker
```

Note that all dependent connections must be created before building as docker.

## Deploy with Azure App Service
The two scripts will do the following things:
1. Create a resource group if not exists.
2. Build and push the image to docker registry.
3. Create an app service plan with the give sku.
4. Create an app with specified name, set the deployment container image to the pushed docker image.
5. Set up the environment variables for the app.

::::{tab-set}
:::{tab-item} Bash
Example command to use bash script:
```shell
bash deploy.sh --path build -i <image_tag> --name my_app_23d8m -r <docker registery> -g <resource_group>
```
See the full parameters by `bash deploy.sh -h`.
:::
:::{tab-item} PowerShell
Example command to use powershell script:
```powershell
.\deploy.ps1 -i <image_tag> --Name my_app_23d8m -r <docker registery> -g <resource_group>
```
See the full parameters by `.\deploy.ps1 -h`.
:::
::::

Note that the `name` will produce a unique FQDN as AppName.azurewebsites.net.


## View and test the web app
The web app can be found via [azure portal](https://ms.portal.azure.com/) 

![img](../../media/cloud/azureml/deploy_appservice_azure_portal_img.png)

After the app created, you will need to go to https://ms.portal.azure.com/ find the app and set up the environment variables
at (Settings>Configuration) or (Settings>Environment variables), then restart the app.

![img](../../media/cloud/azureml/deploy_appservice_set_env_var.png)

The app can be tested by sending a POST request to the endpoint or browse the test page.
::::{tab-set}
:::{tab-item} Bash
```bash
curl https://<name>.azurewebsites.net/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
```
:::
:::{tab-item} PowerShell
```powershell
Invoke-WebRequest -URI https://<name>.azurewebsites.net/score -Body '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -Method POST  -ContentType "application/json"
```
:::
:::{tab-item} Test Page
Browse the app at Overview and see the test page:

![img](../../media/cloud/azureml/deploy_appservice_test_page.png)
:::
::::

Tips:
- Reach deployment logs at (Deployment>Deployment Central) and app logs at (Monitoring>Log stream).
- Reach advanced deployment tools at https://$name.scm.azurewebsites.net/.
- Reach more details about app service at https://learn.microsoft.com/azure/app-service/.

## Next steps
- Try the example [here](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/azure-app-service).