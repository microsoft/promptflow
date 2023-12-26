# Basic eager flow

This example shows how to create a basic eager flow. 

## SDK experience

### 1. Test flow with single line data

Testing flow with function call (no metrics recorded):

```python
from entry import simple_flow

flow_entry(prompt="Python Hello World!")
```

Testing flow with `PFClient`

```python
from promptflow import PFClient

pf = PFClient()
pf.test(flow="./entry.py", inputs={"prompt": "Python Hello World!"})
```

### 2. create flow run with multi line data

```python
from promptflow import PFClient

pf = PFClient()
pf.run(flow="./entry.py", data="./data.jsonl")
```

## CLI experience

### 1. Test flow with single line data

Testing flow/node:

```bash
# test with default input value in entry.py
pf flow test --flow .\entry.py --inputs prompt='write me a python hello world'
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --column-mapping text='${data.text}' --stream
```

## TODO list

- Support @flow.
  - Add @flow decorator.
  - Executor recognize @flow. instead of @tool
- Support output annotation.
- Support specifying @flow function name when executing.
  - We only support 1 @flow function in fixed script "entry.py" for now.
- Support python flow in BatchEngine.
- Line result contract change, no node for eager flow.
- Support flow context:
  - Connection override
  - Streaming
- Aggregation support.
- Connection support.
- API to generate meta.
