---
resources: examples/tutorials/tracing/
---

## Traces

Prompt flow provides the trace feature to capture and visualize the internal execution details for all flows.

For `DAG flow` user can track and visualize node level inputs/outputs of flow execution, it provides critical insights for developer to understand the internal details of execution. 

For `Flex flow` developers, which are using different frameworks (langchain, semantic kernel, OpenAI, kinds of agents) to create LLM based applications, we allow user to instrument their code in a [OpenTelemetry](https://opentelemetry.io/) compatible way, and visualize using UI provided by promptflow devkit.

### LLM Trace
#### **`start_trace()` to enable trace for LLM calls**
Let's start with the simplest example, add single line code to enable trace for LLM calls in your application.
```python
from openai import OpenAI
from promptflow.tracing import start_trace

# start_trace() will print a url for trace detail visualization 
start_trace()

client = OpenAI()

completion = client.chat.completions.create(
  model="gpt-4",
  messages=[
    {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
    {"role": "user", "content": "Compose a poem that explains the concept of recursion in programming."}
  ]
)

print(completion.choices[0].message)
```

With the trace url, user will see a trace list that corresponding to each LLM calls:
![LLM-trace-list](../../../docs/media/trace/LLM-trace-list.png)

Click on line record, the LLM detail will be displayed with chat window experience, together with other LLM call params:
![LLM-trace-detail](../../../docs/media/trace/LLM-trace-detail.png)

More case of adding trace for autogen and langchain:

1. **[Add trace for Autogen](./autogen-groupchat/)**

![autogen-trace-detail](../../../docs/media/trace/autogen-trace-detail.png)

2. **[Add trace for Langchain](./langchain)**

![langchain-trace-detail](../../../docs/media/trace/langchain-trace-detail.png)

#### **`@trace` to allow you trace for any function**
More common scenario is the application has complicated code structure, and developer would like to add trace on critical path that they would like to debug and monitor. 

See the **[math_to_code](./math_to_code.py)** example. Execute below command will get an URL to display the trace records and trace details of each test.

```bash
python math_to_code.py
```

### Flow Traces
If your application is created with DAG flow, all flow test and batch run will be automatically enable trace function. Take the **[chat_with_pdf](../../flows/chat/chat-with-pdf/)** as example. Run `pf flow test --flow .`, each flow test will generate single line in the trace UI:
![flow-trace-record](../../../docs/media/trace/flow-trace-records.png)

Click a record, the trace details will be visualized as tree view.

![flow-trace-detail](../../../docs/media/trace/flow-trace-detail.png)

### Evaluate against batch data
Keep using **[chat_with_pdf](../../flows/chat/chat-with-pdf/)** as example, to trigger a batch run, you can use below commands:

```cmd
pf run create -f batch_run.yaml
```
Or
```cmd
pf run create --flow . --data "./data/bert-paper-qna.jsonl" --column-mapping chat_history='${data.chat_history}' pdf_url='${data.pdf_url}' question='${data.question}'
```
Then you will get a run related trace URL, e.g. http://localhost:52008/v1.0/ui/traces?run=chat_with_pdf_variant_0_20240226_181222_219335

![batch_run_record](../../../docs/media/trace/batch_run_record.png)