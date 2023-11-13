# Create service with flow

You can create your own service with a flow.
This folder contains a example on how to build a service with a flow.
Reference [here](./simple_score.py) for a minimal service example.
The output of score.py will be a json serialized dictionary.
You can use json parser to parse the output.
For example, in powershell:

```powershell
curl -X POST http://127.0.0.1:5000/score --header "Content-Type: application/json" --data '{"flow_input": "some_flow_input", "node_input": "some_node_input"}' | ConvertFrom-Json | ConvertTo-Json
```
