# Entity match rate evaluation

This is a flow evaluates: entity match rate.

Tools used in this flow：
- `python` tool

## Prerequisites

Install promptflow sdk and other dependencies:
```bash
pip install -r requirements.txt
```

### 1. Test flow/node

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --column-mapping ground_truth='${data.ground_truth}' entities='${data.entities}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.
