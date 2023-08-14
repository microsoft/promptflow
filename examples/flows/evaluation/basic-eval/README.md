# Basic Eval
This example shows how to create a basic evaluation flow. 

Tools used in this flow：
- `python` tool

## Prerequisites

Install promptflow sdk and other dependencies in this folder:
```bash
pip install -r requirements.txt
```

## What you will learn

In this flow, you will learn
- how to compose a point based evaluation flow, where you can calculate point-wise metrics.
- the way to log metrics. use `from promptflow import log_metric`
    - see file [aggregate](aggregate.py). TODO.

### 1. Test flow with single line data

Testing flow/node:
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs groundtruth=ABC prediction=ABC

# test node with inputs
pf flow test --flow . --node line_process --inputs groundtruth=ABC prediction=ABC
```

### 2. create flow run with multi line data
There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --data ./data.jsonl --stream
```