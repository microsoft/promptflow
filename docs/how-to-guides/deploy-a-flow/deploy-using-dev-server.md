# Deploy a flow using development server
:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](https://aka.ms/azuremlexperimental).
:::

After create a flow and test it properly, the flow can be served as a http endpoint.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI
We are going to use the [basic-with-connection flow](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/basic-with-connection) as
an example to show how to deploy a flow.

Please ensure you have [create the connection](../manage-connections.md#create-a-connection) required by flow, if not, you could simply create it by running the follow command.
```bash
pf connection create -f .\custom.yml --set configs.api_base=https://<to-be-replaced>.openai.azure.com/ secrets.api_key=<to-be-replaced>
```

The following CLI commands allows you serve a flow folder as an endpoint. By running this command, a [flask](https://flask.palletsprojects.com/en/) app will start in the environment where command is executed, please ensure all prerequisites required by flow have been installed.
```bash
# Serve the flow at localhost:8080
pf flow serve --source <path-to-your-flow-folder> --port 8080 --host localhost
```

The expected result is as follows if the flow served successfully, and the process will keep alive until it be killed manually.

![img](../../media/how-to-guides/deploy_flow.png)
:::
:::{tab-item} VS Code Extension
:sync: VSC
![img](../../media/how-to-guides/vscode_export.png)
![img](../../media/how-to-guides/vscode_export_as_local_app.png)
:::
::::

## Test endpoint
::::{tab-set}
:::{tab-item} Bash
You could open another terminal to test the endpoint with the following command:
```bash
curl http://localhost:8080/score --data '{"text":"Hello world!"}' -X POST  -H "Content-Type: application/json"
```
Test result:

![img](../../media/how-to-guides/test_endpoint_bash.png)
:::
:::{tab-item} PowerShell
You could open another terminal to test the endpoint with the following command:
```powershell
Invoke-WebRequest -URI http://localhost:8080/score -Body '{"text":"Hello world!"}' -Method POST  -ContentType "application/json"
```
Test result:

![img](../../media/how-to-guides/test_endpoint.png)
:::
:::{tab-item} VS Code Extension
:sync: VSC
![img](../../media/how-to-guides/vscode_start_local_app.png)
:::
::::

## Next steps
- Try the example [here](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/deploy.md).
- See how to [deploy a flow using docker](deploy-using-docker.md).
- See how to [deploy a flow using kubernetes](deploy-using-kubernetes.md).
