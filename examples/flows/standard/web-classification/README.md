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

### 4 Bulk Run with multi-line data

```bash
pf run create --flow . --type bulk --data ./data.jsonl --stream
```

```bash
# list run
pf run list
# show run
pf run show -n "202a66f7-3b83-420c-bc0d-2e0a97cd2d99"
```

### 5 Run with classification evaluation flow

create `evaluation` run:
```bash
pf run create --type evaluation --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --inputs_mapping "groundtruth=data.answer,prediction=variant.outputs.category" --variant "202a66f7-3b83-420c-bc0d-2e0a97cd2d99" 
```

```bash
pf run show-details -n c11b8760-4849-4880-a3e2-b6d4d40924f0
pf run show-metrics -n c11b8760-4849-4880-a3e2-b6d4d40924f0
pf run visualize c11b8760-4849-4880-a3e2-b6d4d40924f0
```
