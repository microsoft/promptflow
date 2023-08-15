# How to use exported dockerfile

## Exported Dockerfile Structure

Exported Dockerfile & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
  - ...
- Dockerfile: the dockerfile to build the image
- connections.sqlite: the sqlite database file to store the connections used in the flow
- connections_setup.py: the python script to migrate the connections used in the flow
- start.sh: the script used in `CMD` of `Dockerfile` to start the service
- docker-compose.yaml: a sample compose file to run the service
- README.md: the readme file to describe how to use the dockerfile

## Build Docker image

Like other Dockerfile, you need to build the image first. You can tag the image with any name you want. In this example, we use `promptflow-serve`.

After cd to the output directory, run the command below:

```bash
docker build . -t promptflow-serve
```

## Run Docker image

Run the docker image will start a service to serve the flow inside the container. Service will listen on port 8080.
You can map the port to any port on the host machine as you want.

If the service involves connections, you need to migrate the connections before the first request to the service.
Given api_key in connections are secrets, we have provided a way to migrate them with the `migration-secret` you have provided in export command.

### Manage migration-secret with `docker-secret`

As a pre-requirement of connections migration, you need to create a docker secret named `MIGRATION_SECRET`
to store the migration secret first. Sample command is like below:

```bash
#### Init host machine as a swarm manager
docker swarm init
#### Create a secret to store the migration secret
# You can create the docker secret directly from shell with bash
(read -sp "Enter your migration secret: "; echo $REPLY) | docker secret create MIGRATION_SECRET -
# or you can also create secret from a local file with migration secret as its content, like in Powershell
docker secret create MIGRATION_SECRET <migration_secret_file>
```

You can check below documents for more details:
- [Swam mode overview](https://docs.docker.com/engine/swarm/)
- [Secrets management](https://docs.docker.com/engine/swarm/secrets/)

### Run with `docker-service` [WIP]

To avoid manually migrate the connections, you can use `docker-secret` to manage the migration secret
and `docker-service` to run the service:

```bash
#### Start the service
docker service create --name promptflow-service -p 8080:8080 --secret MIGRATION_SECRET promptflow-serve
```

You can check below documents for more details:
- [Run Docker Engine in swarm mode](https://docs.docker.com/engine/swarm/swarm-mode/)

### Run with `docker-compose`

You can also use `docker-secret` in your compose file and use compose file to start your service:

```bash
#### Deploy the service
docker stack deploy --compose-file=./docker-compose.yaml service1
```

Note that you need to deploy the service to a swarm cluster to use `docker-secret`.
So connections won't be migrated successfully if you run `docker-compose` directly.
More details can be found in the official document:
- [Deploy a stack to a swarm](https://docs.docker.com/engine/swarm/stack-deploy/)

In the sample compose file `docker-compose.yaml` in the output directory, we claim secret `MIGRATION_SECRET`
as external, which means you need to create the secret first before running the compose file.

You can also specify the migration secret file and docker image in the compose file:

```yaml
services:
  promptflow:
    image: <your-image>
...
secrets:
  MIGRATION_SECRET:
    file: <your-migration-secret-file>
```

Official document:
- [Manage secrets in Docker Compose](https://docs.docker.com/compose/compose-file/compose-file-v3/#secrets)
- [Using secrets in Compose](https://docs.docker.com/compose/use-secrets/)

## Test the endpoint
After start the service, you can use curl to test it:

```bash
curl http://localhost:8080/score --data '{"text":"Hello world!"}' -X POST  -H "Content-Type: application/json"
```

## Advanced: Run with `docker run`

If you want to debug or have provided a wrong migration-secret, you can run the docker image directly and manually migrate the connections via below commands:

```bash
docker run -p 8080:8080 promptflow-serve
#### Migrate connections
docker exec -it <container_id> python connections_setup.py --file /connections.sqlite --migration-secret <migration_secret> --clean
```

Note that the command to migrate the connections must be run before any requests to the service.
