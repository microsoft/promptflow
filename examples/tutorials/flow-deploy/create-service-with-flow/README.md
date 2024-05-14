---
resources: examples/tutorials/flow-deploy/create-service-with-flow
category: deployment
weight: 10
---

# Create service with flow

This example shows how to create a simple service with flow.

You can create your own service by utilize `flow-as-function`.

This folder contains a example on how to build a service with a flow.
Reference [here](./simple_score.py) for a minimal service example.
The output of score.py will be a json serialized dictionary.
You can use json parser to parse the output.

## 1. Start the service and put in background

```bash
nohup python simple_score.py &
# Note: added this to run in our CI pipeline, not needed for user.
sleep 10
```

## 2. Test the service with request

Executing the following command to send a request to execute a flow.

```bash
curl -X POST http://127.0.0.1:5000/score --header "Content-Type: application/json" --data '{"flow_input": "some_flow_input", "node_input": "some_node_input"}'
```

Sample output of the request:

```json
{
  "output": {
    "value": "some_flow_input"
  }
}
```

Reference [here](./simple_score.py) for more.
