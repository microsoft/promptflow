# Deploy a flow
A flow can be deployed across multiple platforms, such as a local development service, within a Docker container, onto a Kubernetes cluster, etc.

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
 
- image: ../../media/how-to-guides/appservice.png
  content: "<center><b>Azure App Service</b></center>"
  website: ../../cloud/azureai/deploy-to-azure-appservice.html

```

```{toctree}
:maxdepth: 1
:hidden:

deploy-using-dev-server
deploy-using-docker
deploy-using-kubernetes
```