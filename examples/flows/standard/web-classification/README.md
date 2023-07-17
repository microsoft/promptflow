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

install promptflow-sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1 Create Azure OpenAI or OpenAI connection

```bash
pf connection create --file azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

### 2 Configure the flow with your connection
`flow.dag.yaml` is already configured with connection named `azure_open_ai_connection`.

### 3 Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 4 batch Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --type batch --data ./data.jsonl --stream
# create run using yaml flie
pf run create --file run.yml
```

```bash
# list run
pf run list
# show run
pf run show -n "eff911b7-0a59-4002-8882-86c554c75716"
# show run outputs
pf run show-details -n "eff911b7-0a59-4002-8882-86c554c75716"
```

### 5 Run with classification evaluation flow

create `evaluation` run:
```bash
# create run using command line args
pf run create --type evaluation --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --inputs-mapping "groundtruth=${data.answer},prediction=${batch_run.outputs.category}" --batch-run "eff911b7-0a59-4002-8882-86c554c75716" 
# create run using yaml flie
pf run create --file run_evaluation.yml --batch-run eff911b7-0a59-4002-8882-86c554c75716
```

```bash
pf run show-details -n 60e69d27-3481-461f-aeb6-a78e0c87ea9e
pf run show-metrics -n 60e69d27-3481-461f-aeb6-a78e0c87ea9e
pf run visualize 60e69d27-3481-461f-aeb6-a78e0c87ea9e
```


### 6 Submit run to cloud
```bash
# set default workspace
az account set -s 96aede12-2f73-41cb-b983-6d11a904839b
az configure --defaults group="promptflow" workspace="promptflow-eastus"

# create batch run
pfazure run create --file run.yml --runtime demo-mir
pfazure run stream --name d572ce0f-bd8b-48cb-960a-38dc662a63f0
pfazure run show-details --name d572ce0f-bd8b-48cb-960a-38dc662a63f0
pfazure run show-metrics --name d572ce0f-bd8b-48cb-960a-38dc662a63f0

# create evaluation run
# pfazure run create --file run_evaluation.yml --runtime demo-mir --batch-run d572ce0f-bd8b-48cb-960a-38dc662a63f0
pfazure run create --type evaluation --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --inputs-mapping "groundtruth=${data.answer},prediction=${batch_run.outputs.category}" --batch-run "d572ce0f-bd8b-48cb-960a-38dc662a63f0"  --runtime demo-mir

pfazure run stream --name 4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74
pfazure run show --name 4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74
pfazure run show-details --name 4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74
pfazure run show-metrics --name 4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74
# pfazure run visualize 4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74 
```