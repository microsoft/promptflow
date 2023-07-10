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

### 3 Test flow

```bash
pf flow test --flow . --input data.jsonl
```

### 4 Run with classification evaluation flow

```bash
pf run create --flow . --type bulk --data ./data.jsonl --stream
```

### 5 Run with classification evaluation flow

* Run 'Classification Accuracy Evaluation' from an existing Web Classification flow run
    * step 1: submit a bulk test Web Classification flow
    * step 2: click on 'View run history' to go to all submitted runs page and select a bulk test in bulk runs panel to go to details page
    * step 3: click on 'New evaluation', select one or more variants and the classification evaluation flow from Sample or Customer evaluation flows. Then set connections, input mappings and submit

```bash
TODO
```
