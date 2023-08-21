# Groundedness Evaluation

This is a flow leverage llm to eval percieved intelligence.
Perceived intelligence is the degree to which a bot can impress the user with its responses, by showing originality, insight, creativity, knowledge, and adaptability.

Tools used in this flow：
- `python` tool
- built-in `llm` tool

### 1. Test flow/node

```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .
```

### 2. create flow run with multi line data

```bash
pf run create --flow . --data ./data.jsonl --stream
```

