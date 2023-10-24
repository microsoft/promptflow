# Classification Accuracy Evaluation

This is a flow illustrating how to evaluate the performance of a classification system. It involves comparing each prediction to the groundtruth and assigns a "Correct" or "Incorrect" grade, and aggregating the results to produce metrics such as accuracy, which reflects how good the system is at classifying the data.

Tools used in this flow：
- `python` tool

## What you will learn

In this flow, you will learn
- how to compose a point based evaluation flow, where you can calculate point-wise metrics.
- the way to log metrics. use `from promptflow import log_metric`
    - see file [calculate_accuracy.py](calculate_accuracy.py)

### 0. Setup connection

Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

### 1. Test flow/node

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs groundtruth=APP prediction=APP

# test node with inputs
pf flow test --flow . --node grade --inputs groundtruth=groundtruth prediction=prediction
```

### 2. create flow run with multi line data
There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --data ./data.jsonl --column-mapping groundtruth='${data.groundtruth}' prediction='${data.prediction}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

### 3. create run against other flow run

Learn more in [web-classification](../../standard/web-classification/README.md)

