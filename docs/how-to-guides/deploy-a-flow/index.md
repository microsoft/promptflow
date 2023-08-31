# Deploy a flow
A flow can be deployed across multiple platforms, such as a local development service, within a Docker container, onto a Kubernetes cluster, etc.

```{gallery-grid}
:grid-columns: 1 2 2 3
- image: ../../media/how-to-guides/local.png
  content: "<center><b>Development server</b></center>"
  website: deploy-local.html

- image: ../../media/how-to-guides/docker.png
  content: "<center><b>Docker</b></center>"
  website: deploy-using-docker.html
  
- image: ../../media/how-to-guides/kubernetes.png
  content: "<center><b>Kubernetes</b></center>"
  website: deploy-using-kubernetes.html

```

We also support deploy promptflow with azure services:
- [Deploy to Azure App Service](../../cloud/azureai/deploy-to-azure-appservice.md)

```{toctree}
:maxdepth: 1
:hidden:

deploy-local
deploy-using-docker
deploy-using-kubernetes
```