# Deploy a flow using Docker
:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

There are two steps to deploy a flow using docker:
1. Build the flow in docker format.
2. Build and run the docker image.
 
## Build a flow as docker format

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

Use the command below to build a flow as docker format:
```bash
pf flow build --source <path-to-your-flow-folder> --output <your-output-dir> --format docker
```
:::
:::{tab-item} VS Code Extension
:sync: VSC

Click the button below to build a flow as docker format:
![img](../../media/how-to-guides/vscode_export_as_docker.png)
:::
::::

Note that all dependent connections must be created before exporting as docker.


### Docker format folder structure

Exported Dockerfile & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
  - ...
- connections: the folder contains yaml files to create all related connections
  - ...
- Dockerfile: the dockerfile to build the image
- start.sh: the script used in `CMD` of `Dockerfile` to start the service
- settings.json: a json file to store the settings of the docker image
- README.md: Simple introduction of the files

## Deploy with Docker
We are going to use the [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/) as
an example to show how to deploy with docker.

Please ensure you have [create the connection](../manage-connections.md#create-a-connection) required by flow, if not, you could
refer to [Setup connection for web-classifiction](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification#1-setup-connection).

## Build a flow as docker format app

Use the command below to build a flow as docker format app:

```bash
pf flow build --source ../../flows/standard/web-classification --output build --format docker
```

Note that all dependent connections must be created before exporting as docker.

You can refer to [Build a flow](../build-a-flow.md) for more details about `pf flow builf`.

### Build Docker image

Like other Dockerfile, you need to build the image first. You can tag the image with any name you want. In this example, we use `promptflow-serve`.

Run the command below to build image:

```bash
docker build build -t web-classification-serve
```

### Run Docker image

Run the docker image will start a service to serve the flow inside the container. 

#### Connections
If the service involves connections, all related connections will be exported as yaml files and recreated in containers.
Secrets in connections won't be exported directly. Instead, we will export them as a reference to environment variables:
```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
type: open_ai
name: open_ai_connection
module: promptflow.connections
api_key: ${env:OPEN_AI_CONNECTION_API_KEY} # env reference
```
You'll need to set up the environment variables in the container to make the connections work.

### Run with `docker run`

You can run the docker image directly set via below commands:
```bash
# The started service will listen on port 8080.You can map the port to any port on the host machine as you want.
docker run -p 8080:8080 -e OPEN_AI_CONNECTION_API_KEY=<secret-value> web-classification-serve
```

### Test the endpoint
After start the service, you can use curl to test it:

```bash
curl http://localhost:8080/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
```

## Next steps
- Try the example [here](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/docker).
- See how to [deploy a flow using kubernetes](deploy-using-kubernetes.md).