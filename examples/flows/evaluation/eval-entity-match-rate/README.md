# Entity match rate evaluation

This is a flow evaluates: entity match rate.

Tools used in this flow：
- `python` tool


### 1. Test flow/node

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --stream
```

