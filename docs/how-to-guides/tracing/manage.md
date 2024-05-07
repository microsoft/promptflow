# Manage traces

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Prompt flow provides several trace toolkits in `promptflow-devkit`. This page will introduce how to delete traces in local storage with CLI/SDK.

## Local trace management

### Delete

Prompt flow provides capability to delete traces in local storage, user can delete traces by collection (a bucket of traces, can be specified with `start_trace`), time range or prompt flow run with both CLI and SDK:

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
