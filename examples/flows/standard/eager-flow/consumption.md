# Consumption

## flow as func

```python
from promptflow import load_flow

my_flow = load_flow(source="./flow.dag.yaml")
result = my_flow(text="Java Hello World!")

from my_flow 
result = my_flow(text="Java Hello World!")
```



## flow test

```python
from promptflow import PFClient

pf_client = PFClient()
pf_client.test(flow="./flow.dag.yaml", inputs={"text": "Java Hello World!"})


from promptflow import PFClient

pf_client = PFClient()
pf_client.test(flow=my_flow, inputs={"text": "Java Hello World!"})
# or
result = my_flow(text="Java Hello World!")
```

## flow run

```python
from promptflow import PFClient

pf_client = PFClient()
pf_client.run(flow="./flow.dag.yaml", data="./data.jsonl")


from promptflow import PFClient

pf_client = PFClient()
pf_client.run(flow=my_flow, data="./data.jsonl")
```



## serve

```python
from flask import Flask, jsonify, request
import json

class SimpleScoreApp(Flask):
    pass

app = SimpleScoreApp(__name__)

f = load_flow("./echo_connection_flow/")

@app.route("/score", methods=["POST"])
def score():
    data = json.loads(request.get_data())
    f(**data)


from flow import my_flow

@app.route("/score", methods=["POST"])
def score():
    data = json.loads(request.get_data())
    my_flow(**data)

```

## flow as component

```python
from azure.ai.ml import dsl

# Register flow as a component
flow_component = load_component("standard/web-classification/flow.dag.yaml")

@dsl.pipeline
def pipeline_func_with_flow(data):
    flow_node = flow_component(
        data=data,
        url="${data.url}",
        connections={
            "summarize_text_content": {
                "connection": "azure_open_ai_connection",
                "deployment_name": "text-davinci-003",
            },
        },
    )
    flow_node.compute = "cpu-cluster"

from azure.ai.ml import dsl
from my_flow import my_flow


@dsl.pipeline
def pipeline_func_with_flow(data):
    flow_node = my_flow(
        data=data,
        url="${data.url}",
        connections={
            "summarize_text_content": {
                "connection": "azure_open_ai_connection",
                "deployment_name": "text-davinci-003",
            },
        },
    )
    flow_node.compute = "cpu-cluster"
```

## sharing

```bash
pf flow build --source <path-to-your-flow-folder> --output <your-output-dir> --format xxx
```

```bash
pf flow build --source <path-to-flow-func> --name <flow-func-name> --output <your-output-dir> --format xxx
```
