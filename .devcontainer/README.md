# Promptflow base images

This folder contains Dockerfile for promptflow images.

## Dev-container config

File devcontainer.json points to a local image defined in DOCKERFILE.

Inside the image:

- default python with latest promptflow, promptflow-tools.

### How to build image

Command to build the Dockerfile inside this folder:

```cmd
docker build -t promptflow_container .
```

### How to list image

Command to list the images:

```cmd
docker image ls
```

### How to run the image

Local run using this command:

```cmd
docker run -it promptflow_container
``
