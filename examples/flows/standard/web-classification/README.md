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
# replace your api key in azure_openai.yml before run this command
pf connection create --file azure_openai.yml
```

### 2 Configure the flow with your connection
`flow.dag.yaml` is already configured with connection named `azure_open_ai_connection`.

### 3 Test flow with single line data

```bash
pf flow test --flow . --input data.jsonl
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
