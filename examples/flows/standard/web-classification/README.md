# Web Classification

This is a flow demonstrating multi-class classification with LLM. Given an url, it will classify the url into one web category with just a few shots, simple summarization and classification prompts.

## Tools used in this flow
- LLM Tool
- Python Tool

## What you will learn

In this flow, you will learn
- how to compose a classification flow with LLM.
- how to feed few shots to LLM classifier.

## Prerequisites

Install prompt-flow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Create Azure OpenAI or OpenAI connection

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

### 2. Configure the flow with your connection
`flow.dag.yaml` is already configured with connection named `azure_open_ai_connection`.

### 3. Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
# test with user specified inputs
pf flow test --flow . --inputs url='https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h'
```

### 4. Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --stream
# create run using yaml file
pf run create --file run.yml --stream
```

```bash
# list run
pf run list
# show run
pf run show --name "web_classification_variant_1_20230724_173442_973403"
# show run outputs

pf run show-details --name "web_classification_variant_1_20230724_173442_973403"
```

### 5. Run with classification evaluation flow

create `evaluation` run:
```bash
# create run using command line args
pf run create --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run "web_classification_variant_1_20230724_173442_973403" --stream
# create run using yaml file
pf run create --file run_evaluation.yml --run "web_classification_variant_1_20230724_173442_973403" --stream
```

```bash
pf run show-details --name "classification_accuracy_eval_default_20230724_173628_639497"
pf run show-metrics --name "classification_accuracy_eval_default_20230724_173628_639497"
pf run visualize --name "classification_accuracy_eval_default_20230724_173628_639497"
```


### 6. Submit run to cloud
```bash
# set default workspace
az account set -s 96aede12-2f73-41cb-b983-6d11a904839b
az configure --defaults group="promptflow" workspace="promptflow-eastus"

# create run
pfazure run create --flow . --data ./data.jsonl --stream --runtime demo-mir --subscription 96aede12-2f73-41cb-b983-6d11a904839b -g promptflow -w promptflow-eastus
pfazure run create --flow . --data ./data.jsonl --stream # serverless compute
pfazure run create --file run.yml --runtime demo-mir
pfazure run create --file run.yml --stream # serverless compute


pfazure run stream --name "web_classification_default_20230724_173705_462735"
pfazure run show-details --name "web_classification_default_20230724_173705_462735"
pfazure run show-metrics --name "web_classification_default_20230724_173705_462735"

# create evaluation run
pfazure run create --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run "web_classification_default_20230724_173705_462735" --runtime demo-mir
pfazure run create --file run_evaluation.yml --run "web_classification_default_20230724_173705_462735" --stream # serverless compute

pfazure run stream --name "classification_accuracy_eval_default_20230724_173843_841080"
pfazure run show --name "classification_accuracy_eval_default_20230724_173843_841080"
pfazure run show-details --name "classification_accuracy_eval_default_20230724_173843_841080"
pfazure run show-metrics --name "classification_accuracy_eval_default_20230724_173843_841080"
pfazure run visualize --name "classification_accuracy_eval_default_20230724_173843_841080" 
```