# Deploy flow using Azure App Service

[Azure App Service](https://learn.microsoft.com/azure/app-service/) is an HTTP-based service for hosting web applications, REST APIs, and mobile back ends.
Promptflow has provided scripts (`deploy.sh` for bash and `deploy.ps1` for powershell) to help deploy the docker image to Azure App Service.

Example command to use bash script:
```bash
bash deploy.sh --path <> -i <image_tag> -r "promptflow.azurecr.io" -g <resource_group>
```

Example command to use powershell script:
```powershell
.\deploy.ps1 -i <image_tag> -r "promptflow.azurecr.io" -g <resource_group>
```

See the full parameters by `bash deploy.sh -h` or `.\deploy.ps1 -h`.

After the app created, you will need to go to https://ms.portal.azure.com/ find the app and set up the environment variables
at (Settings>Configuration) or (Settings>Environment variables), then restart the app.

Tips:
- Reach deployment logs at (Deployment>Deployment Central) and app logs at (Monitoring>Log stream).
- Reach advanced deployment tools at https://$name.scm.azurewebsites.net/.
- Reach more details about app service at https://learn.microsoft.com/azure/app-service/.