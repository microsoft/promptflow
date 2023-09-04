# Deploy flow using Kubernetes
This example demos how to deploy [web-classification](../../../flows/standard/web-classification/README.md) as a Kubernetes app.

Please ensure you have [create the connection](https://github.com/microsoft/promptflow/blob/main/docs/how-to-guides/manage-connections.md) required by flow, if not, you could
refer to [Setup connection for web-classifiction](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification#1-setup-connection). 

Additionally, please ensure that you have installed all the required dependencies. You can refer to the "Prerequisites" section in the README of the [web-classification](../../../flows/standard/web-classification/README.md#Prerequisites) for a comprehensive list of prerequisites and installation instructions.

## Build a flow as docker format

Use the command below to build a flow as docker format app:

```bash
pf flow build --source ../../flows/standard/web-classification --output build --format docker
```

Note that all dependent connections must be created before exporting as docker.

## Deploy with Kubernetes
### Build Docker image

Like other Dockerfile, you need to build the image first. You can tag the image with any name you want. In this example, we use `web-classification-serve`.

Then run the command below:

```bash
cd build
docker build . -t web-classification-serve
```

### Push the container image to a registry.
After building the image, it's essential to tag it with the appropriate name for your container registry. For example:
```bash
docker tag web-classification-serve <your-docker-hub-id>/web-classification-serve
```
Once you've successfully logged into the container registry, you can push the tagged docker image to enable public access and usage.
```bash
docker login <your-docker-hub-id>
docker push <your-docker-hub-id>/web-classification-serve
```

### Create Kubernetes deployment yaml.
The Kubernetes deployment yaml file serves as a blueprint for orchestrating your docker container within a Kubernetes pod. It meticulously outlines essential details, including the container image, port configurations, environment variables, and various settings. We have presented a [basic deployment template](./deployment.yaml) for your convenience, which you can effortlessly tailor to your specific requirements.

You need encode the secret using base64 firstly and input the encoded value as 'open-ai-connection-api-key' in the deployment configuration, for example:
```bash
echo -n 'secret' | base64
```

### Apply the deployment.
Before you can deploy your application, ensure that you have set up a Kubernetes cluster and installed [kubectl](https://kubernetes.io/docs/reference/kubectl/) if it's not already installed. In this documentation, we will use [Minikube](https://minikube.sigs.k8s.io/docs/) as an example. To start the cluster, execute the following command:
```bash
minikube start
```
Once your Kubernetes cluster is up and running, you can proceed to deploy your application by using the following command:
```bash
kubectl apply -f deployment.yaml
```
This command will create the necessary pods to run your application within the cluster.

### Retrieve flow service logs of the container
The kubectl logs command is used to retrieve the logs of a container running within a pod, which can be useful for debugging, monitoring, and troubleshooting applications deployed in a Kubernetes cluster.

```bash
kubectl -n <your-namespace> logs <pod-name>
```

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

### Test the endpoint
- Option1:

  Once you've started the service, you can establish a connection between a local port and a port on the pod. This allows you to conveniently test the endpoint from your local terminal.
  To achieve this, execute the following command:

  ```bash
  kubectl port-forward <pod_name> <local_port>:<container_port>
  ```
  With the port forwarding in place, you can use the curl command to initiate the endpoint test:

  ```bash
  curl http://localhost:<local_port>/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
  ```

- Option2:
  ```minikube service web-classification-service --url -n <your-namespace>``` runs as a process, creating a tunnel to the cluster. The command exposes the service directly to any program running on the host operating system.

  The command above will generate a URL, which you can click to interact with the flow service in your web browser. Alternatively, you can use the following command to test the endpoint: 

    ```bash
  curl http://<url-above>/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
  ```