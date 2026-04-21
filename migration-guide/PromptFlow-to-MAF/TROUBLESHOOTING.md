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

MAF core packages are GA (1.0.1) — `--pre` is no longer needed for
`agent-framework` and `agent-framework-foundry`. However,
`agent-framework-orchestrations` and `agent-framework-azure-ai-search` are
still in preview and require `--pre`.

---

### I'm getting dependency conflicts after upgrading from an RC version

RC installs (`1.0.0rc*` or `1.0.0b*`) are incompatible with the GA release.
The GA packages enforce `>=1.0.1,<2` dependency floors.

Clean install:

    pip uninstall agent-framework agent-framework-core agent-framework-openai agent-framework-foundry -y
    pip install agent-framework>=1.0.1 agent-framework-foundry>=1.0.1

Preview packages (orchestrations, Azure AI Search, and connectors like
`agent-framework-copilotstudio`) still require `--pre` on a separate
install command:

    pip install agent-framework-orchestrations agent-framework-azure-ai-search --pre

Do not mix `--pre` and non-`--pre` packages in a single install command.

---

### `agent-framework-azure-ai` cannot be found

There is no package called `agent-framework-azure-ai`. For Foundry project
endpoints, use `agent-framework-foundry`:

    pip install agent-framework-foundry

Import from `agent_framework.foundry`.

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

### `FoundryChatClient` is not connecting to my Foundry project

Verify your `.env` contains the correct Foundry project endpoint. The endpoint
format is `https://<resource>.services.ai.azure.com`:

    from agent_framework.foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["FOUNDRY_MODEL"],
        credential=DefaultAzureCredential(),
    )

If using `DefaultAzureCredential`, ensure you are logged in (`az login`) or
that a managed identity is assigned to your compute.

---

### I want to use managed identity instead of `DefaultAzureCredential`

See `phase-4-migrate-ops/4b-deployment/managed_identity.md` for step-by-step
instructions. The short version: use `ManagedIdentityCredential()` as the
`credential=` argument to `FoundryChatClient()` when deploying to Azure.

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
An executor that is not reachable from the `start_executor` via `add_edge()`
will never run. Double-check your edge definitions.

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

- **No start executor set** — you must pass `start_executor=` to
  `WorkflowBuilder(...)`.
- **Type mismatch on an edge** — the output type of executor A does not match
  the input type of executor B. Check that `WorkflowContext[T_Out]` in the
  upstream executor matches the handler parameter type in the downstream one.
- **Duplicate executor ID** — each executor must have a unique `id=` value.
- **Unreachable executor** — an executor passed to `add_edge()` but not
  connected to the graph via any edge path from the start executor.

---

### Fan-in aggregation is not waiting for all parallel branches

`add_fan_in_edges()` waits for all listed sources to complete before firing.
Make sure every parallel executor in the fan-out is also listed in the fan-in:

    .add_fan_out_edges(dispatch, [path_a, path_b])
    .add_fan_in_edges([path_a, path_b], aggregate)  # both must be listed

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

Make sure **both** `configure_azure_monitor()` and `configure_otel_providers()`
are called **before** any `workflow.run()` call — not after, and not inside a
handler. They must run at application startup:

    from azure.monitor.opentelemetry import configure_azure_monitor
    from agent_framework.observability import configure_otel_providers

    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
    )
    configure_otel_providers()
    # workflow.run() calls go after this

`configure_azure_monitor()` sets up the Application Insights exporter.
`configure_otel_providers()` enables MAF's built-in instrumentation so that
executor transitions, agent calls, and LLM requests produce workflow-level
spans. Without it, you will see Application Insights metadata but no
workflow-specific trace data.

Also verify the connection string is correct: Azure Portal → your Application
Insights resource → Overview → Connection String.

---

### Traces show Application Insights data but no workflow steps

You called `configure_azure_monitor()` but not `configure_otel_providers()`.
The Azure Monitor function only handles transport, but MAF workflows require
`configure_otel_providers()` from `agent_framework.observability` to generate
executor-level spans. See the entry above for the correct two-step setup.

---

### Online endpoint deployment stays in `Updating` state or fails

Check the deployment logs for the actual error:

    az ml online-deployment get-logs \
      --endpoint-name maf-endpoint --name blue \
      --resource-group <rg> --workspace-name <ws>

Common causes:

1. **`score.py` import error** — a missing dependency or an incorrect
   `sys.path` in `init()`. Make sure every package used by `score.py` and
   the workflow file is listed in `conda.yml`.
2. **`init()` raises an exception** — the managed online endpoint calls
   `init()` once at container startup. If it throws, the container is
   marked unhealthy and the deployment fails. Run your workflow locally
   first to rule out runtime errors.
3. **Quota exceeded** — the subscription does not have enough quota for the
   requested instance type. Check regional quota in the Azure Portal or
   run `az ml online-deployment list --endpoint-name <name>`.

---

### `az ml online-endpoint invoke` returns a scoring error

The endpoint is running but `run()` in `score.py` raised an exception.
Retrieve the full traceback from the deployment logs (see above).

Frequent causes:

- **Empty or malformed request body** — the `run(raw_data)` function expects
  a JSON string with a `"question"` key. Verify your request file:

      echo '{"question": "What is MAF?"}' > request.json
      az ml online-endpoint invoke \
        --name maf-endpoint --request-file request.json \
        --resource-group <rg> --workspace-name <ws>

- **Wrong workflow file** — `score.py` defaults to
  `phase-2-rebuild/01_linear_flow.py`. Override via the
  `MAF_WORKFLOW_FILE` environment variable in `deployment.yml`.
- **Workflow produced no output** — see the
  "`workflow.run()` returns a result but `get_outputs()` is an empty list"
  section above.

---

### Managed identity authentication fails on the online endpoint

If `score.py` uses `DefaultAzureCredential` or `ManagedIdentityCredential`
to call Foundry or other Azure services, ensure:

1. A system-assigned or user-assigned managed identity is enabled on the
   online endpoint.
2. The identity has the required role assignments (e.g.
   `Cognitive Services OpenAI User` on the Foundry resource).

See `phase-4-migrate-ops/4b-deployment/managed_identity.md` for full
instructions.

---

### How do I update an existing deployment without downtime?

Use `az ml online-deployment update` with the same deployment name. The
managed endpoint performs a rolling update. To do a blue/green swap instead,
create a second deployment and shift traffic:

    az ml online-endpoint update --name maf-endpoint \
      --traffic "blue=0 green=100" \
      --resource-group <rg> --workspace-name <ws>

---

## Reference links

- [Azure ML managed online endpoints overview](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online)
- [Deploy and score a model with a managed online endpoint](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints)
- [Troubleshoot online endpoint deployments](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-troubleshoot-online-endpoints)
- [Managed online endpoint VM SKU list](https://learn.microsoft.com/en-us/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list)

---

## Still stuck?

- [MAF GitHub Issues](https://github.com/microsoft/agent-framework/issues/)
- [MAF Workflows documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/executors)
- [Azure AI Evaluation SDK reference](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python)
- Open an issue in this repo using the [migration issue template](../.github/ISSUE_TEMPLATE/migration-issue.md)
