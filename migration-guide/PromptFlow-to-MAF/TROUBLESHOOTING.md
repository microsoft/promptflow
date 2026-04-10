# Troubleshooting

Common issues encountered when migrating from Prompt Flow to MAF, grounded
in the MAF 1.0 GA release (2 Apr 2026) and the official API documentation.
If your issue is not listed here, open a GitHub issue using the [migration issue template](../.github/ISSUE_TEMPLATE/migration-issue.md).

---

## Installation

### `ModuleNotFoundError: No module named 'agent_framework'`

The package was not installed, or an old RC install is conflicting.

Uninstall any previous version first, then reinstall cleanly:

    pip uninstall agent-framework agent-framework-core agent-framework-foundry -y
    pip install agent-framework>=1.0.0

MAF 1.0 is GA — `--pre` is no longer needed for core packages.

---

### I'm getting dependency conflicts after upgrading from an RC version

RC installs (`1.0.0rc*` or `1.0.0b*`) are incompatible with the GA release.
The GA packages enforce `>=1.0.0,<2` dependency floors.

Clean install:

    pip uninstall agent-framework agent-framework-core agent-framework-openai agent-framework-foundry -y
    pip install agent-framework>=1.0.0

If you are using preview connectors (e.g. `agent-framework-copilotstudio`,
`agent-framework-ollama`, `agent-framework-devui`), those still require `--pre`
on a separate install command:

    pip install agent-framework-copilotstudio --pre

Do not mix `--pre` and non-`--pre` packages in a single install command.

---

### `agent-framework-azure-ai` cannot be found

This package was removed in 1.0. The embedding and Foundry model endpoint
surfaces moved to `agent-framework-foundry`:

    pip install agent-framework-foundry

Import from `agent_framework.foundry` instead of `agent_framework.azure_ai`.

---

## Authentication & connections

### `401 Unauthorized` when calling Azure OpenAI

Your API key is missing, empty, or pointing at the wrong resource. Check:

1. Your `.env` file exists at the project root and is populated.
2. `load_dotenv()` is called before any client is instantiated.
3. `AZURE_OPENAI_ENDPOINT` ends with `.openai.azure.com/` (trailing slash matters).
4. `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` matches the exact deployment name in
   Azure Portal → your OpenAI resource → Model deployments (case-sensitive).

Verify your key length is non-zero:

    echo "Key length: $(echo $AZURE_OPENAI_API_KEY | wc -c)"

---

### `AzureOpenAIChatClient` is hitting the wrong endpoint

If you have both `OPENAI_API_KEY` and `AZURE_OPENAI_*` set in your environment,
the client defaults to OpenAI (not Azure) when `OPENAI_API_KEY` is present.
To force Azure routing, pass the credential explicitly:

    from agent_framework.azure import AzureOpenAIChatClient
    from azure.identity import AzureCliCredential

    client = AzureOpenAIChatClient(
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment_name=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        credential=AzureCliCredential(),
    )

---

### I want to use managed identity instead of an API key

See `phase-4-migrate-ops/4b-deployment/managed_identity.md` for step-by-step
instructions. The short version: pass `credential=ManagedIdentityCredential()`
to `AzureOpenAIChatClient()` and remove `AZURE_OPENAI_API_KEY` from your
environment variables.

---

### I'm connecting to a Foundry project endpoint but `AzureOpenAIChatClient` doesn't work

`AzureOpenAIChatClient` targets raw Azure OpenAI Service endpoints
(`https://<resource>.openai.azure.com`). For Foundry project endpoints
(`https://<resource>.services.ai.azure.com`), use `FoundryChatClient`:

    from agent_framework.foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["FOUNDRY_MODEL"],
        credential=DefaultAzureCredential(),
    )

---

## Workflows & executors

### `workflow.run()` returns a result but `get_outputs()` is an empty list

The terminal executor is not yielding a workflow output. Check three things:

**1. The context annotation includes a workflow output type.**

Incorrect — sends a message but yields nothing:

    async def handle(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text)

Correct — yields a final workflow output:

    async def handle(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(text)

**2. `ctx.yield_output()` is actually called.**
Check for early returns or unhandled exceptions that might skip the call.

**3. The executor is connected to the workflow graph.**
An executor that is registered but not reachable from `set_start_executor()`
via `add_edge()` will never run. Double-check your edge definitions.

---

### `TypeError` or `AttributeError` on `Message(text=...)`

The `text=` parameter on the `Message` constructor was removed in 1.0.
Build messages using `contents=[...]` instead:

Incorrect:

    message = Message(role="user", text="Hello")

Correct:

    message = Message(role="user", contents=["Hello"])

Plain strings inside `contents=[]` are automatically normalised into text
content, so `contents=["Hello"]` is the simplest form.

---

### My `add_edge()` condition function never fires

Condition functions receive the exact message passed to `ctx.send_message()`.
Make sure the value and the condition logic match precisely:

    # Executor sends:
    await ctx.send_message("safe")

    # Condition must match that exact string:
    def is_safe(message: str) -> bool:
        return message == "safe"

A common mistake is sending a tagged string (e.g. `"billing||<question>"`)
but writing the condition as if the message is a plain label. See
`phase-2-rebuild/07_multi_agent.py` for a worked example of the tagged
string pattern.

---

### My workflow runs but hangs and never completes

The most common cause is a circular edge definition — executor A sends to B,
and B sends back to A, creating an infinite loop. MAF uses a superstep
execution model and will keep iterating until it reaches the `max_iterations`
limit (default: 100), then raise an error.

Check your `add_edge()` calls for cycles. If you need a loop intentionally,
set `max_iterations` explicitly on `WorkflowBuilder`:

    WorkflowBuilder(name="MyWorkflow", max_iterations=10)

---

### `WorkflowBuilder` raises a validation error at `.build()`

MAF validates the workflow graph at build time. Common causes:

- **No start executor set** — you must call `.set_start_executor("Name")`.
- **Type mismatch on an edge** — the output type of executor A does not match
  the input type of executor B. Check that `WorkflowContext[T_Out]` in the
  upstream executor matches the handler parameter type in the downstream one.
- **Duplicate executor name** — each `.register_executor()` call must use a
  unique `name=` value.
- **Unreachable executor** — an executor is registered but not connected to
  the graph via any `add_edge()`, `add_fan_out_edges()`, or `add_fan_in_edges()`.

---

### Fan-in aggregation is not waiting for all parallel branches

`add_fan_in_edges()` waits for all listed sources to complete before firing.
Make sure every parallel executor in the fan-out is also listed in the fan-in:

    .add_fan_out_edges("Dispatch", ["PathA", "PathB"])
    .add_fan_in_edges(["PathA", "PathB"], "Aggregate")  # both must be listed

If one branch is missing from `add_fan_in_edges()`, the aggregator may fire
early with a partial result.

---

## Parity validation

### `TypeError: SimilarityEvaluator() missing required argument: 'model_config'`

`model_config` became a required argument in azure-ai-evaluation GA (1.16+).

Incorrect:

    evaluator = SimilarityEvaluator()

Correct:

    model_config = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
    }
    evaluator = SimilarityEvaluator(model_config=model_config, threshold=3)

---

### Similarity scores are unexpectedly low (< 2.0)

Check the keyword arguments passed to the evaluator. Using the wrong kwargs
causes the evaluator to compare the wrong fields and score near zero:

Incorrect:

    evaluator(answer=maf_answer, ground_truth=pf_answer)

Correct:

    evaluator(query=question, response=maf_answer, ground_truth=pf_answer)

Also verify that the `pf_output` column in your CSV contains the actual
text output from your PF app — not the input question.

---

### The parity check script is very slow

Use `parity_check_batch.py` instead of `parity_check.py`. The batch version
runs all rows concurrently with `asyncio.gather()` and is significantly
faster for test suites with 20+ rows.

---

## Tracing & deployment

### No traces appearing in Application Insights

Make sure `configure_azure_monitor()` is called **before** any `workflow.run()`
call — not after, and not inside a handler. It must run at application startup:

    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    )
    # workflow.run() calls go after this

Also verify the connection string is correct: Azure Portal → your Application
Insights resource → Overview → Connection String.

---

### `uvicorn` starts but `/ask` returns 500

The most common cause is that `app.py` loaded the wrong workflow file, or the
target file does not define a module-level `workflow` object. By default the
deployment sample uses `phase-2-rebuild/01_linear_flow.py`. To deploy your own
workflow, set `MAF_WORKFLOW_FILE`:

    export MAF_WORKFLOW_FILE=phase-2-rebuild/05_rag_flow.py

Also check the Application Insights trace for the full exception — the 500
response body is intentionally generic to avoid leaking internals.

---

### `az containerapp create` fails with an image pull error

The Container App cannot reach your Azure Container Registry. Ensure:

1. `--registry-server` matches your ACR login server exactly
   (`<name>.azurecr.io`).
2. The Container App's managed identity (or admin credentials) has the
   `AcrPull` role on the registry.
3. The image tag pushed by `az acr build` matches the tag in `--image`.

---

## Still stuck?

- [MAF GitHub Issues](https://github.com/microsoft/agent-framework/issues/)
- [MAF Workflows documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/executors)
- [Azure AI Evaluation SDK reference](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python)
- Open an issue in this repo using the [migration issue template](../.github/ISSUE_TEMPLATE/migration-issue.md)
