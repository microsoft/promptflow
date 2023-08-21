# Intent-copilot
This example shows how to create a flow from existing langchain code.
Reference [code](./intent.py). 

## Prerequisites

install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

Ensure you have put enough your azure open ai endpoint key in .env file.
```bash
cat .env
```

## Run flow in local

1. init flow directory - create promptflow folder from existing python file
```bash
pf flow init --flow . --entry intent.py --function extract_intent --prompt-template chat_prompt=user_intent_zero_shot.jinja2
```
The generated files:
- extract_intent_tool.py: Wrap the func `extract_intent` in the `intent.py` script into a [Python tool](https://promptflow.azurewebsites.net/tools-reference/python-tool.html).
- flow.dag.yaml: Describes the DAG(Directed Acyclic Graph) of this flow.
- .gitignore: File/folder in the flow to be ignored.

Please enter the input of the flow/node to `flow.dag.yaml`, like below:
```yaml
inputs:   # Enter the flow inputs
  customer_info:
    type: string
  history:
    type: list
outputs:
  output:
    type: string
    reference: ${extract_intent.output}
nodes:
- name: chat_prompt
  type: prompt
  source:
    type: code
    path: user_intent_zero_shot.jinja2
  inputs:  # Enter the inputs of this node
    customer_info: ${inputs.customer_info}
    chat_history: ${inputs.history}
```

2. create needed custom connection
```bash
pf connection create -f .env --name custom_connection
```

3. test flow locally with single line input
```bash
pf flow test --flow . --input ./data/denormalized-flat.jsonl
```

4. run with multiple lines input
```bash
pf run create --flow . --data ./data
```

5. list/show 

```bash
# list created run
pf run list
# get a sample completed run name
name=$(pf run list | jq '.[] | select(.name | contains("intent_copilot")) | .name'| head -n 1 | tr -d '"')
# show run
pf run show --name $name
# show specific run detail, top 3 lines
pf run show-details --name $name -r 3
```

6. evaluation

```bash
# create evaluation run
pf run create --flow ../../evaluation/classification-accuracy-eval --data ./data --column-mapping groundtruth='${data.intent}' prediction='${run.outputs.output}' --run $name
```

```bash
# get the evaluation run in previous step
eval_run_name=$(pf run list | jq '.[] | select(.name | contains("classification_accuracy_eval")) | .name'| head -n 1 | tr -d '"')
# show run
pf run show --name $eval_run_name
# show run output
pf run show-details --name $eval_run_name -r 3
```

6. visualize
```bash
# visualize in browser
pf run visualize --name $eval_run_name # your evaluation run name
```

## Deploy 

### Serve as a local test app

```bash
pf flow serve --source . --port 5123 --host localhost
```
Visit http://localhost:5213 to access the test app.

### Export

#### Export as docker
```bash
# pf flow export --source . --format docker --output ./package
```