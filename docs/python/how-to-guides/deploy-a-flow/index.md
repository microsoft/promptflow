# Deploy a flow
A flow can be deployed to multiple platforms, such as a local development service, Docker container, Kubernetes cluster, etc.

```{gallery-grid}
:grid-columns: 1 2 2 3
- image: ../../media/how-to-guides/local.png
  content: "<center><b>Development server</b></center>"
  website: deploy-using-dev-server.html

- image: ../../media/how-to-guides/docker.png
  content: "<center><b>Docker</b></center>"
  website: deploy-using-docker.html
  
- image: ../../media/how-to-guides/kubernetes.png
  content: "<center><b>Kubernetes</b></center>"
  website: deploy-using-kubernetes.html
 
```

We also provide guides to deploy to cloud, such as azure app service:

```{gallery-grid}
:grid-columns: 1 2 2 3

- image: ../../media/how-to-guides/appservice.png
  content: "<center><b>Azure App Service</b></center>"
  website: ../../cloud/azureai/deploy-to-azure-appservice.html

```

We are working on more official deployment guides for other hosting providers, and welcome user submitted guides.

```{toctree}
:maxdepth: 1
:hidden:

deploy-using-dev-server
deploy-using-docker
deploy-using-kubernetes
distribute-flow-as-executable-app
```