# Flow Serve & Export

## Serve a flow as local http endpoint

The following CLI commands allows you serve a flow as an endpoint.

Below is taking [basic-with-connection](../../flows/standard/basic-with-connection) flow as example.
- Before we start, please ensure you have create the connection required by flow.
See [connections](../../connections/) for more details about connection.


Serve a flow as endpoint:
```bash
pf flow serve --source ../../flows/standard/basic-with-connection --port 8080 --host localhost
```

Test the endpoint:
```bash
curl http://localhost:8080/score --data '{"text":"Hello world!"}' -X POST  -H "Content-Type: application/json"
```

## Export a flow as docker format

Note that we must have all dependent connections created before exporting as docker:

```bash
pf connection create --file ../../flows/standard/basic-with-connection/custom.yml
```

The following CLI commands allows you export a flow as a sharable folder with a Dockerfile and its dependencies.

```bash
pf flow export --source ../../flows/standard/basic-with-connection --output <your-output-dir> --format docker
```

You'll be asked to input a secret encryption key when running this command, which needs to be provided when you run the built docker image.
You can also provide the key via `--encryption-key` directly or passing it with a file via `--encryption-key-file`.

More details about how to use the exported docker can be seen in `<your-output-dir>/README.md`. 
Part of sample output are under [./linux](./linux/) so you can also check [this README](./linux/README.md) directly.

## Export a flow as portable package format

WIP.