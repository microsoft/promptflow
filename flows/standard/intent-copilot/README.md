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
pf connection create -f .env --type custom --name custom_connection
```

3. run locally with single line input
```bash
pf flow test --flow . --input ./data/denormalized-flat.jsonl --env .env
```

4. bulk run with multiple lines input
```bash
pf run create --type bulk --input ./data/denormalized-flat.jsonl --output ./outputs/ --env .env
```

6. evaluation
```bash
pf run create --type evaluate --flow ../../evaluate/classification_accuracy_evaluation --input ./data/denormalized-flat.jsonl --bulk-run-output ./outputs/ --eval-output ./outputs/eval_output.jsonl --column-mapping "groundtruth=data.intent,prediction=variants.output.output"
```

6. visualize
```bash
pf run visualize --evaluations your_evaluate_run_name
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