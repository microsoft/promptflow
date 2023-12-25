# Basic eager flow

This example shows how to create a basic eager flow. 

## SDK experience

### 1. Test flow with single line data

Testing flow with function call (no metrics recorded):

```python
from entry import simple_flow


```

Testing flow with `PFClient`

```python
from entry import simple_flow


```

### 2. create flow run with multi line data

```python

```

## CLI experience

### 1. Test flow with single line data

Testing flow/node:

```bash
# test with default input value in entry.py
pf flow test --flow .
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --column-mapping groundtruth='${data.groundtruth}' prediction='${data.prediction}' --stream
```

## TODO list

- Support output annotation.
- Line result contract change, no node for eager flow.
- Aggregation support.
- Connection support.
- API to generate meta.
