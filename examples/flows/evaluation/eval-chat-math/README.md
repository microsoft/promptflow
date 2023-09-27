# Eval chat math

This example shows how to evaluate the answer of math questions, which can compare the output results with the standard answers numerically.

Learn more on corresponding [tutorials](../../../tutorials/flow-fine-tuning-evaluation/promptflow-quality-improvement.md)

Tools used in this flow：
- `python` tool

## Prerequisites

Install promptflow sdk and other dependencies in this folder:
```bash
pip install -r requirements.txt
```

### 1. Test flow with single line data

Testing flow/node:
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs groundtruth=123 prediction=123

# test node with inputs
pf flow test --flow . --node line_process --inputs groundtruth=123 prediction=123
```

### 2. create flow run with multi line data
There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --data ./data.jsonl --stream
```