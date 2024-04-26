# Tracing

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Prompt flow provides the trace feature to capture and visualize the internal execution details for all flows.

For `DAG flow`, user can track and visualize node level inputs/outputs of flow execution, it provides critical insights for developer to understand the internal details of execution. 

For `Flex flow` developers, who might use different frameworks (langchain, semantic kernel, OpenAI, kinds of agents) to create LLM based applications, prompt flow allow user to instrument their code in a [OpenTelemetry](https://opentelemetry.io/) compatible way, and visualize using UI provided by promptflow devkit.

## Instrumenting user's code

### Enable trace for LLM calls
Let's start with the simplest example, add single line code **`start_trace()`** to enable trace for LLM calls in your application.
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

Running above python script will produce below example output:
```
Prompt flow service has started...
You can view the traces from local: http://localhost:<port>/v1.0/ui/traces/?#collection=basic
```

Click the trace url, user will see a trace list that corresponding to each LLM calls:
![LLM-trace-list](../../media/trace/LLM-trace-list.png)


Click on one line record, the LLM detail will be displayed with chat window experience, together with other LLM call params:
![LLM-trace-detail](../../media/trace/LLM-trace-detail.png)

### Trace on any function
A more common scenario is the application has complicated code structure, and developer would like to add trace on critical path that they would like to debug and monitor. 

See the **[math_to_code](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/tracing/math_to_code.py)** example on how to use **`@trace`**. 

Execute below command will get an URL to display the trace records and trace details of each test.

```python
from promptflow.tracing import trace
# trace your function
@trace
def code_gen(client: AzureOpenAI, question: str) -> str:
    sys_prompt = (
        "I want you to act as a Math expert specializing in Algebra, Geometry, and Calculus. "
        "Given the question, develop python code to model the user's question. "
        "Make sure only reply the executable code, no other words."
    )
    completion = client.chat.completions.create(
        model=os.getenv("CHAT_DEPLOYMENT_NAME", "gpt-35-turbo"),
        messages=[
            {
                "role": "system",
                "content": sys_prompt,
            },
            {"role": "user", "content": question},
        ],
    )
    raw_code = completion.choices[0].message.content
    result = code_refine(raw_code)
    return result
```

```shell
python math_to_code.py
```

## Trace visualization in flow test and batch run

### Flow test
If your application is created with DAG flow, all flow test and batch run will be automatically enable trace function. Take the **[chat_with_pdf](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-with-pdf/)** as example. 

Run `pf flow test --flow .`, each flow test will generate single line in the trace UI:
![flow-trace-record](../../media/trace/flow-trace-records.png)

Click a record, the trace details will be visualized as tree view.

![flow-trace-detail](../../media/trace/flow-trace-detail.png)

### Evaluate against batch data
Keep using **[chat_with_pdf](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-with-pdf)** as example, to trigger a batch run, you can use below commands:

```shell
pf run create -f batch_run.yaml
```
Or
```shell
pf run create --flow . --data "./data/bert-paper-qna.jsonl" --column-mapping chat_history='${data.chat_history}' pdf_url='${data.pdf_url}' question='${data.question}'
```
Then you will get a run related trace URL, e.g. http://localhost:<port>/v1.0/ui/traces?run=chat_with_pdf_20240226_181222_219335

![batch_run_record](../../media/trace/batch_run_record.png)

### Search

Trace UI supports simple Python expression for search experience, which is demonstrated in below GIF:

![advanced_search](../../media/trace/advanced-search.gif)

Currently it supports bool operator `and` and `or`, compare operator `==`, `!=`, `>`, `>=`, `<`, `<=`; and the fields that are searchable: `name`, `kind`, `status`, `start_time`, `cumulative_token_count.total`, `cumulative_token_count.prompt` and `cumulative_token_count.completion`. You can find the hints by clicking the button right to the search edit box.

![search_hint](../../media/trace/trace-ui-search-hint.png)

## Local trace management

### Delete

Prompt flow provides capability to delete traces in local storage, user can delete traces by collection, time range or prompt flow run with both CLI and SDK:

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf trace delete --collection <collection-name>  # delete specific collection
pf trace delete --collection <collection-name> --started-before '2024-03-01T16:00:00.123456'  # delete traces started before the time in specific collection
pf trace delete --run <run-name>  # delete traces originated from specific prompt flow run
```
:::

:::{tab-item} SDK
:sync: SDK

```python
from promptflow.client import PFClient

pf = PFClient()
pf.traces.delete(collection="<collection-name>")  # delete specific collection
pf.traces.delete(collection="<collection-name>", started_before="2024-03-01T16:00:00.123456")  # delete traces started before the time in specific collection
pf.traces.delete(run="<run-name>")  # delete traces originated from specific prompt flow run
```

:::

::::

## Trace with prompt flow

Prompt flow tracing works not only for general LLM application, but also for more frameworks like `autogen` and `langchain`:

1. Example: **[Add trace for LLM](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/tracing/llm)**

![llm-trace-detail](../../media/trace/llm-app-trace-detail.png)

2. Example: **[Add trace for Autogen](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/tracing/autogen-groupchat/)**

![autogen-trace-detail](../../media/trace/autogen-trace-detail.png)

3. Example: **[Add trace for Langchain](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/tracing/langchain)**

![langchain-trace-detail](../../media/trace/langchain-trace-detail.png)
