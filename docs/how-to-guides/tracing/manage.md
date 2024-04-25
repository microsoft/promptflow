# Visualize and manage traces

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Prompt flow provides several trace toolkits in `promptflow-devkit`, so that user can better capture and visualize the internal execution details for all flows:

- For `DAG flow`, user can track and visualize node level inputs/outputs of flow execution, it provides critical insights for developer to understand the internal details of execution. 
- For `Flex flow` developers, who might use different frameworks (langchain, semantic kernel, OpenAI, kinds of agents) to create LLM based applications, prompt flow allow user to instrument their code in a [OpenTelemetry](https://opentelemetry.io/) compatible way, and visualize using UI provided by promptflow devkit.

## Trace visualization in flow test and batch run

With `promptflow-devkit` installed, running python script with `start_trace` will produce below example output:

```bash
Prompt flow service has started...
You can view the traces from local: http://localhost:<port>/v1.0/ui/traces/?#collection=basic
```

Click the trace url, user will see a trace list that corresponding to each LLM calls:
![LLM-trace-list](../../media/trace/LLM-trace-list.png)


Click on one line record, the LLM detail will be displayed with chat window experience, together with other LLM call params:
![LLM-trace-detail](../../media/trace/LLM-trace-detail.png)

When combine trace and flow, trace UI provides a more comprehensive view of the flow execution, user can easily track the flow execution details, and debug the flow execution issues.

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
