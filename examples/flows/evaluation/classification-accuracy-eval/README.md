# Classification Accuracy Evaluation

This is a flow illustrating how to evaluate the performance of a classification system. It involves comparing each prediction to the groundtruth and assigns a "Correct" or "Incorrect" grade, and aggregating the results to produce metrics such as accuracy, which reflects how good the system is at classifying the data.

Tools used in this flow：
- `python` tool

## What you will learn

In this flow, you will learn
- how to compose a point based evaluation flow, where you can calculate point-wise metrics.
- the way to log metrics. use `from promptflow import log_metric`
    - see file [calculate_accuracy.py](calculate_accuracy.py)

### 1. Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with multi line data
There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --data ./data.jsonl --stream
```

### 3. create run against other flow run

Learn more in [web-classification](../../standard/web-classification/README.md)

