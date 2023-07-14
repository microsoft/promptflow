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

Doc to be added.

## Export a flow as portable package format

WIP.