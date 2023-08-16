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

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

## Getting Started

### 1. Setup connection

Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

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
pf flow test --flow . --inputs url='https://www.youtube.com/watch?v=kYqRtjDBci8'
```

### 4. Run with multi-line data

```bash
# create run using command line args
pf run create --flow . --data ./data.jsonl --stream

# (Optional) create a random run name
run_name="web_classification_"$(openssl rand -hex 12)
# create run using yaml file, run_name will be used in following contents, --name is optional
pf run create --file run.yml --stream --name $run_name
```

```bash
# list run
pf run list
# show run
pf run show --name $run_name
# show run outputs
pf run show-details --name $run_name
```

### 5. Run with classification evaluation flow

create `evaluation` run:
```bash
# (Optional) save previous run name into variable, and create a new random run name for furthur use
prev_run_name=$run_name
run_name="classification_accuracy_"$(openssl rand -hex 12)
# create run using command line args
pf run create --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run $prev_run_name --stream
# create run using yaml file, --name is optional
pf run create --file run_evaluation.yml --run $prev_run_name --stream --name $run_name
```

```bash
pf run show-details --name $run_name
pf run show-metrics --name $run_name
pf run visualize --name $run_name
```


### 6. Submit run to cloud
```bash
# set default workspace
az account set -s <your_subscription_id>
az configure --defaults group=<your_resource_group_name> workspace=<your_workspace_name>

# create run
pfazure run create --flow . --data ./data.jsonl --stream --runtime demo-mir --subscription <your_subscription_id> -g <your_resource_group_name> -w <your_workspace_name>
# pfazure run create --flow . --data ./data.jsonl --stream # serverless compute

# (Optional) create a new random run name for furthur use
run_name="web_classification_"$(openssl rand -hex 12)

# create run using yaml file, --name is optional
pfazure run create --file run.yml --runtime demo-mir --name $run_name
# pfazure run create --file run.yml --stream --name $run_name # serverless compute


pfazure run stream --name $run_name
pfazure run show-details --name $run_name
pfazure run show-metrics --name $run_name


# (Optional) save previous run name into variable, and create a new random run name for furthur use
prev_run_name=$run_name
run_name="classification_accuracy_"$(openssl rand -hex 12)

# create evaluation run, --name is optional
pfazure run create --flow ../../evaluation/classification-accuracy-eval --data ./data.jsonl --column-mapping groundtruth='${data.answer}' prediction='${run.outputs.category}' --run $prev_run_name --runtime demo-mir
pfazure run create --file run_evaluation.yml --run $prev_run_name --stream --name $run_name --runtime demo-mir

pfazure run stream --name $run_name
pfazure run show --name $run_name
pfazure run show-details --name $run_name
pfazure run show-metrics --name $run_name
pfazure run visualize --name $run_name
```