# Intent-copilot
This example shows how to create a flow from existing langchain [code](./intent.py). 

## Prerequisites

install promptflow-sdk and other dependencies:
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
pf flow init --flow . --entry intent.py --function extract_intent --prompt-template user_prompt_template=user_intent_zero_shot.md
```
TODO introduce the generated files

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
# show run
pf run show --name "<flow_name>"
# show specific run detail, top 3 lines
pf run show-details --name "<flow_name>" -r 3
```

6. evaluation

```bash
# create evaluation run
pf run create --flow ../../evaluation/classification-accuracy-eval --data ./data --column-mapping "groundtruth=${data.intent},prediction=${run.outputs.output}" --run "3dbe8954-cfe6-41c5-aa5f-03e57e678cc5" 
```

```bash
# show run
pf run show --name "<flow_name>"
# show run output
pf run show-details --name "<flow_name>" -r 3
```

6. visualize
```bash
# visualize in browser
pf run visualize --name "<flow_name>" # your evaluation run name
```

## Tuning node variant
TODO: Compare the zero_shot & few_shot prompt.

1. change the dag to include node variants

2. validate the dag
```bash
pf validate --flow .
```

3. run the node_variant
```bash
pf run create --flow . --node_variant node.variant1
```

## Deploy 

### Serve as a local test app

```bash
pf flow serve --source . --port 5123 --host localhost
```

TODO: introduce the browser based test app 

### Export

#### Export as package

```bash
pf flow export --source . --format package --path ./package
```

#### Export as docker
```bash
pf flow export --source . --format docker --path ./package
```