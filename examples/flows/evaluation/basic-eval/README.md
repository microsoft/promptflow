# Basic Eval
This example shows how to create a basic evaluation flow. 

Tools used in this flow：
- `python` tool

## What you will learn

In this flow, you will learn
- how to compose a point based evaluation flow, where you can calculate point-wise metrics.
- the way to log metrics. use `from promptflow import log_metric`
    - see file [aggregate](aggregate.py). TODO.

### 1. Test flow with single line data

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with batch data
There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --type batch --data ./data.jsonl --stream
```