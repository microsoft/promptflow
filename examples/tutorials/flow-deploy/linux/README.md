# How to use exported dockerfile

## Exported Dockerfile Structure

Exported Dockerfile & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
  - ...
- Dockerfile: the dockerfile to build the image
- connections.sqlite: the sqlite database file to store the connections used in the flow
- connections_setup.py: the python script to migrate the connections used in the flow
- README.md: the readme file to describe how to use the dockerfile

## Build Docker image

Like other Dockerfile, you need to build the image first. You can tag the image with any name you want. In this example, we use `promptflow-serve`.

After cd to the output directory, run the command below:

```bash
docker build -t promptflow-serve .
```

## Run Docker image

Run the docker image will start a service to serve the flow inside the container. Service will listen on port 8080.
You can map the port to any port on the host machine as you want.

You have 3 options to run the docker image. They use the same script to migrate the connections used in the flow:

```bash
#### --file: the path to the sqlite database file, will be copied to /db.sqlite on build
#### --encrypt-key: the encrypt key used to encrypt the api key in the connections, must be the same as the one
####   provided in export
#### --encrypt-key-file: use a file to pass the encrypt key instead of command line argument
#### --clean: remove the sqlite database file after migration
python migrate.py --file /db.sqlite --encrypt-key <encrypt_key> --clean
```

### Option 1: Run with `docker run`

This is the simplest way to run the docker image, but you need to manually migrate the connections used in the flow.

```bash
docker run -p 8080:8080 promptflow-serve
#### Migrate connections
docker exec -it <container_id> python connections_setup.py --file /connections.sqlite --encrypt-key <encrypt_key> --clean
```

Note that the command to migrate the connections must be run before any requests to the service.

### Option 2: Run with `docker-service`

To avoid manually migrate the connections, you can use `docker-secret` to manage the encryption key
and `docker-service` to run the service:

```bash
#### Init host machine as a swarm manager
docker swarm init
#### Create a secret to store the encryption key
# You can also use `docker secret create ENCRYPTION_KEY <encrypt_key_file>`
echo "<encrypt_key>" | docker secret create ENCRYPTION_KEY -
#### Start the service
docker service create --name promptflow-service -p 8080:8080 --secret ENCRYPTION_KEY promptflow-serve
```

You can check below documents for more details:
- [Swam mode overview](https://docs.docker.com/engine/swarm/)
- [Secrets management](https://docs.docker.com/engine/swarm/secrets/)
- [Run Docker Engine in swarm mode](https://docs.docker.com/engine/swarm/swarm-mode/)

### Option 3: Run with `docker-compose`

You can also use `docker-compose` to run the service but related document is not ready yet.

Official document: [Manage secrets in Docker Compose](https://docs.docker.com/compose/compose-file/compose-file-v3/#secrets)
