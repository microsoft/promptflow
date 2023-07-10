# Basic
A basic standard flow that calls azure open ai with only python tools which only depends on environment variables. 

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

- run locally with single line input
```bash
pf flow test --flow . --input data.jsonl
```
- bulk run with multiple lines input
```bash
pf run create --type bulk --input ./data/denormalized-flat.jsonl --output ./outputs/ --env .env
```
- evaluation
```bash
pf run create --type evaluate --flow ../../evaluate/classification_accuracy_evaluation --input ./data/denormalized-flat.jsonl --bulk-run-output ./outputs/ --eval-output ./outputs/eval_output.jsonl --column-mapping "groundtruth=data.intent,prediction=variants.output.output"
```
- visualize
```bash
pf run visualize --evaluations your_evaluate_run_name
```