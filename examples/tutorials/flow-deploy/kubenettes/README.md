# Deploy flow using Kubernetes
This example demos how to deploy [web-classification](../../flows/standard/web-classification/README.md) as a Kubernetes app.

## Build a flow as docker format app

Use the command below to build a flow as docker format app:

```bash
pf flow build --source ../../examples/flows/standard/web-classification --output build --format docker
```

Note that all dependent connections must be created before exporting as docker.

## Deploy with Kubernetes
### Build Docker image

Like other Dockerfile, you need to build the image first. You can tag the image with any name you want. In this example, we use `web-classification-serve`.

After cd to the output directory, run the command below:

```bash
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
The Kubernetes deployment yaml file serves as a blueprint for orchestrating your docker container within a Kubernetes pod. It meticulously outlines essential details, including the container image, port configurations, environment variables, and various settings. Presented below is a basic deployment template for your convenience, which you can effortlessly tailor to your specific requirements.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-classification-serve-app
spec:
  selector:
    matchLabels:
      app: web-classification-serve-app
  replicas: 1
  template:
    metadata:
      labels:
        app: web-classification-serve-app
    spec:
      containers:
      - name: web-classification-serve-container
        image: <your-docker-hub-id>/web-classification-serve-update
        ports:
        - containerPort: <container_port>
```

### Apply the Deployment.
Before you can deploy your application, ensure that you have set up a Kubernetes cluster and installed [kubectl](https://kubernetes.io/docs/reference/kubectl/) if it's not already installed. In this documentation, we will use [Minikube](https://minikube.sigs.k8s.io/docs/) as an example. To start the cluster, execute the following command:
```bash
minikube start
```
Once your Kubernetes cluster is up and running, you can proceed to deploy your application by using the following command:
```bash
kubectl apply -f deployment.yaml
```
This command will create the necessary pods to run your application within the cluster.

### Access the container shell to initiate the service
Prior to testing the endpoint, we must launch a service within the container to serve the flow.

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

#### Run with `kubectl exec`
The ```kubectl exec -it``` command is a commonly used command in Kubernetes for executing commands inside a running container. To commence the service, utilize the following commands:
```bash
kubectl exec -it <pod_name> -- /bin/bash -c "export OPEN_AI_CONNECTION_API_KEY=<secret-value> && ./start.sh"
```

### Test the endpoint
Once you've started the service, you can establish a connection between a local port and a port on the pod. This allows you to conveniently test the endpoint from your local terminal.
To achieve this, execute the following command:

```bash
kubectl port-forward <pod_name> <local_port>:<container_port>
```
With the port forwarding in place, you can use the curl command to initiate the endpoint test:

```bash
curl http://localhost:<local_port>/score --data '{"url":"https://play.google.com/store/apps/details?id=com.twitter.android"}' -X POST  -H "Content-Type: application/json"
```
