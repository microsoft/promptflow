# Skills — PromptFlow-to-MAF Migration Guide

Instructions for AI coding agents working on the Prompt Flow → Microsoft Agent Framework migration guide.

---

## Context

Prompt Flow is being retired. This folder contains a 5-phase, hands-on migration guide with runnable Python samples that move a Prompt Flow workload to **Microsoft Agent Framework (MAF) 1.0 GA**.

Target audience: teams running Prompt Flow on Microsoft Foundry or Azure Machine Learning.

---

## AI-Assisted Migration with the Copilot Skill

This repository includes a **Copilot skill file** at [`.github/skills/promptflow-to-maf/SKILL.md`](../../.github/skills/promptflow-to-maf/SKILL.md) that enables AI coding agents (such as GitHub Copilot in VS Code) to **automatically convert** your Prompt Flow `flow.dag.yaml` into a runnable Microsoft Agent Framework project.

### What the Skill Does

The skill teaches the AI agent how to:

1. **Parse your `flow.dag.yaml`** and all referenced source files (`.jinja2` templates, `.py` nodes, `requirements.txt`).
2. **Map every Prompt Flow node** to its MAF equivalent (`Executor`, `Agent`, `WorkflowBuilder`, etc.) using a built-in conversion table.
3. **Generate a complete MAF project** in a sibling `<your-flow>-maf/` folder — including workflow code, `.env.example`, `requirements.txt`, and a runnable test script.
4. **Handle advanced patterns** — chat history, multimodal inputs, fan-out/fan-in, conditional branching, evaluation flows with aggregation, and multi-agent handoffs.
5. **Preserve prompts verbatim** — system prompts, Jinja2 templates, and LLM parameters (`temperature`, `max_tokens`, etc.) are carried over exactly.

### How to Use It

#### Prerequisites

- **VS Code** with the [GitHub Copilot Chat](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat) extension installed.
- This repository cloned locally and opened as your workspace (the skill is auto-discovered from `.github/skills/`).

#### Step-by-Step

1. **Open your Prompt Flow folder** in VS Code — navigate to the directory containing your `flow.dag.yaml`.

2. **Open GitHub Copilot Chat** (Ctrl+Shift+I or the Copilot icon in the sidebar).

3. **Ask Copilot to convert your flow.** Use a prompt like:

   ```
   Convert this Prompt Flow to Microsoft Agent Framework
   ```

   or be more specific:

   ```
   Migrate the flow in examples/flows/chat/chat-basic to MAF
   ```

   The skill activates automatically when it detects migration-related intent (e.g., "convert promptflow", "migrate flow.dag.yaml", "PF to agent-framework").

4. **Copilot reads your flow**, maps each node, and generates the MAF project files in a new `<flow-name>-maf/` folder alongside your original flow.

5. **Review the generated code.** The output includes:
   - `workflow.py` (or numbered sample files) — Executor classes and `WorkflowBuilder` wiring
   - `requirements.txt` — only the needed `agent-framework-*` packages
   - `.env.example` — environment variable template for your credentials
   - `test_<name>.py` — runnable script to verify the workflow

6. **Set up and run:**

   ```bash
   cd <flow-name>-maf/
   pip install -r requirements.txt
   cp .env.example .env   # fill in your credentials
   python test_<name>.py
   ```

### What the Skill Covers

| Prompt Flow Pattern | Skill Handles It? |
|---|---|
| Linear LLM chains | Yes |
| Chat flows with history | Yes |
| Conditional branching (`activate_config`) | Yes |
| Parallel execution (fan-out / fan-in) | Yes |
| RAG (Embed + Vector Lookup + LLM) | Yes |
| Python tool nodes | Yes |
| Multimodal inputs (images) | Yes |
| Evaluation flows (`aggregation: true`) | Yes |
| Multi-agent handoffs | Yes |
| Custom Python packages imported by nodes | Yes — copied into output folder |

### Tips

- **Attach your flow files** — if Copilot doesn't read your flow automatically, attach `flow.dag.yaml` and key source files to the chat for context.
- **Iterate** — you can ask follow-up questions like "add error handling to the LLM executor" or "switch from API key auth to managed identity".
- **The original flow is never modified** — all generated files go into the new `-maf/` folder.
- **Evaluation flows** are automatically split into a per-row workflow, an aggregation function, and an `EvalRunner` orchestrator.

> **Note:** The skill file is designed for AI coding agents. You do not need to read or edit `SKILL.md` yourself — it is consumed by Copilot automatically when the workspace is loaded.

---

## AI-Assisted Online Endpoint Deployment with the Copilot Skill

A second Copilot skill at [`.github/skills/maf-online-endpoint/SKILL.md`](../../.github/skills/maf-online-endpoint/SKILL.md) enables AI coding agents to **automatically generate deployment configuration files** and **deploy a MAF workflow** as an Azure ML managed online endpoint — to either an Azure Machine Learning workspace or an Azure AI Foundry hub-based project.

### What the Skill Does

The skill teaches the AI agent how to:

1. **Inspect your workflow file** — read the `workflow.py` (or equivalent) to discover imports, environment variables, and credential patterns (API key vs. managed identity).
2. **Gather deployment parameters** — interactively ask for subscription ID, resource group, workspace/project name, endpoint name, VM SKU, and workflow-specific environment variables.
3. **Generate a complete `online-deployment/` directory** containing all files needed for a managed online endpoint:
   - `score.py` — scoring script with `init()`/`run()` pattern, importing the workflow factory
   - `conda.yml` — conda environment with Python 3.11, `agent-framework`, and workflow-specific packages
   - `endpoint.yml` — endpoint configuration (name, auth mode)
   - `deployment.yml` — deployment template with `${VAR}` placeholders for environment variables
   - `deploy.sh` — Bash deploy script (Linux/macOS); on Windows, the agent runs `az` CLI commands directly in PowerShell
   - `.gitignore` — prevents rendered YAML files containing secrets from being committed
4. **Render and deploy** — substitute placeholders with actual values, create the endpoint, create the deployment, and run a smoke test.
5. **Assign RBAC** (when needed) — for managed-identity workflows (Foundry/`DefaultAzureCredential`), assign `Cognitive Services User` on the AI Services resource.

### Deployment Targets

| Target | Description |
|--------|-------------|
| **Azure Machine Learning workspace** | Standalone AML workspace — provide subscription, resource group, and workspace name |
| **Azure AI Foundry project** | Hub-based AI project — the project name is used as the workspace name for `az ml` commands |

Both targets produce identical generated files and use the same `az ml` CLI commands.

### How to Use It

#### Prerequisites

- **VS Code** with the [GitHub Copilot Chat](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat) extension installed.
- This repository cloned locally and opened as your workspace.
- **Azure CLI** installed with the `ml` extension (`az extension add -n ml`).
- An existing MAF workflow (e.g., generated by the conversion skill above).

#### Step-by-Step

1. **Open your MAF workflow project** in VS Code — navigate to the directory containing your `workflow.py`.

2. **Open GitHub Copilot Chat** (Ctrl+Shift+I or the Copilot icon in the sidebar).

3. **Ask Copilot to deploy your workflow.** Use a prompt like:

   ```
   Deploy this workflow as an online endpoint
   ```

   or be more specific:

   ```
   Create a managed online endpoint for examples/flows/standard/describe-image-maf
   ```

   The skill activates automatically when it detects deployment-related intent (e.g., "deploy MAF workflow", "create online endpoint", "deploy agent as endpoint").

4. **Copilot asks for deployment details** — it will interactively prompt you for:
   - Deployment target (AML workspace or AI Foundry project)
   - Subscription ID, resource group, workspace/project name
   - Endpoint name and VM SKU
   - Workflow-specific credentials (API keys, endpoints, model deployment names)

5. **Copilot generates all deployment files** in an `online-deployment/` subdirectory:

   ```
   <your-workflow>/
     workflow.py
     online-deployment/
       score.py
       conda.yml
       endpoint.yml
       deployment.yml
       deploy.sh
       .gitignore
   ```

6. **Copilot renders and deploys** — it substitutes placeholders, runs `az ml online-endpoint create` and `az ml online-deployment create`, then invokes the endpoint with a smoke test.

7. **Review the results.** Copilot reports the scoring URI and endpoint status.

### Generated Files Reference

| File | Purpose |
|------|---------|
| `score.py` | Scoring script — `init()` imports the workflow factory; `run()` creates a fresh workflow per request to avoid concurrency errors |
| `conda.yml` | Conda environment — Python 3.11 with only the packages your workflow needs |
| `endpoint.yml` | Endpoint name and auth mode (`key` by default) |
| `deployment.yml` | Deployment template with `${VAR}` placeholders for environment variables, instance type, and request settings |
| `deploy.sh` | Bash deploy script for Linux/macOS (on Windows, the agent runs commands directly in PowerShell) |
| `.gitignore` | Excludes `deployment-rendered.yml` which may contain secrets |

### Key Design Decisions

- **One workflow per request** — `score.py` calls the `create_workflow()` factory on every request, avoiding `RuntimeError: Workflow is already running` on concurrent requests.
- **Path resolution** — since `deployment.yml` lives in `online-deployment/`, it uses `conda_file: conda.yml` (same directory) and `code: ..` (parent = project root). The scoring script path is `online-deployment/score.py` relative to the code root.
- **Request timeout** — set to 60 seconds (vs. the 5-second AML default) to accommodate LLM call latency.
- **Security** — rendered YAML files with substituted secrets are `.gitignore`d. API keys are injected as deployment environment variables, not baked into code.

### Credential Patterns

| Pattern | Env Vars | RBAC Needed? |
|---------|----------|--------------|
| **Azure OpenAI (API key)** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` | No |
| **Foundry (managed identity)** | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` | Yes — `Cognitive Services User` on the AI Services resource |
| **RAG (AI Search)** | Above + `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_INDEX_NAME`, `AZURE_AI_SEARCH_API_KEY` | Depends on LLM auth pattern |

### Example Prompts

```
Deploy this MAF workflow as an online endpoint to my AI Foundry project
```

```
Create an online endpoint deployment for the describe-image workflow
```

```
I need to deploy my agent-framework workflow to Azure ML
```

### Tips

- **Run from the project root** — the `az ml online-deployment create` command must be run from the directory containing `workflow.py`, not from inside `online-deployment/`.
- **Windows users** — `deploy.sh` requires Bash; Copilot automatically uses PowerShell string replacement on Windows instead of `envsubst`.
- **Check deployment logs** — if the endpoint returns errors, run `az ml online-deployment get-logs --name blue --endpoint-name <name>` to view container logs.
- **RBAC propagation** — after assigning `Cognitive Services User` for managed-identity workflows, wait 5–10 minutes before invoking the endpoint.
- **Iterate** — you can ask follow-up questions like "switch to managed identity auth" or "add Application Insights tracing to the endpoint".

> **Note:** The skill file is designed for AI coding agents. You do not need to read or edit `SKILL.md` yourself — it is consumed by Copilot automatically when the workspace is loaded.

---

## Repository Layout

```
migration-guide/PromptFlow-to-MAF/
├── README.md                  # Top-level overview and setup instructions
├── TROUBLESHOOTING.md         # Common migration errors and fixes
├── requirements.txt           # Python dependencies (MAF 1.0 GA, eval SDK, etc.)
├── .env.example               # Environment variable template
├── .github/ISSUE_TEMPLATE/    # Issue template for migration problems
├── phase-1-audit/             # Export PF flow YAML; map nodes to MAF equivalents
│   ├── README.md
│   └── node-mapping.md        # Full PF → MAF concept mapping table
├── phase-2-rebuild/           # Re-implement flows using WorkflowBuilder + Executor
│   ├── README.md
│   └── 01–07_*.py             # Progressive samples (linear → multi-agent)
├── phase-3-validate/          # Side-by-side parity scoring with Azure AI Eval SDK
│   ├── README.md
│   ├── parity_check.py        # Single-row parity scorer
│   └── parity_check_batch.py  # Concurrent batch parity scorer
├── phase-4-migrate-ops/       # Tracing, deployment, CI/CD
│   ├── 4a-tracing/            # OpenTelemetry + Application Insights setup
│   ├── 4b-deployment/         # AML managed online endpoint (score.py, conda.yml)
│   └── 4c-cicd/               # GitHub Actions quality gate (evaluate.yml)
└── phase-5-cutover/           # Traffic switch + PF decommissioning script
    ├── README.md
    └── cutover.sh             # Automated (or dry-run) PF retirement
```

---

## Migration Phases — Quick Reference

| Phase | Goal | Key Output |
|-------|------|------------|
| **1 — Audit & Map** | Understand and document the existing PF flow | Exported `flow.dag.yaml`, completed node-mapping table |
| **2 — Rebuild** | Re-implement in MAF using `WorkflowBuilder` + `Executor` | Working `.py` files mirroring PF behaviour |
| **3 — Validate** | Confirm semantic parity with `SimilarityEvaluator` | `parity_results.csv` with mean score ≥ 3.5 |
| **4 — Migrate Ops** | Replace PF operational infra (tracing, hosting, CI/CD) | App Insights traces, Container App, GitHub Actions gate |
| **5 — Cut Over** | Route traffic to MAF; retire PF endpoints | `cutover.sh` executed; PF connections deleted |

Always work through phases in order. Do not skip ahead.

---

## Core MAF Concepts

These are the foundational abstractions agents should understand when generating or modifying code in this guide:

| Concept | Description |
|---------|-------------|
| **Executor** | A class with a `@handler` method that performs one logical step (replaces a PF "node"). |
| **WorkflowBuilder** | Fluent builder that registers executors and wires them with `.add_edge()`, `.add_fan_out_edges()`, `.add_fan_in_edges()`, then `.build()`. |
| **WorkflowContext** | Type-parameterised context passed to handlers: `WorkflowContext[SendType]` to send downstream, `WorkflowContext[Never, YieldType]` to yield final output, `WorkflowContext[SendType, YieldType]` for both. |
| **Agent** | Created via `Agent(client=FoundryChatClient(...), name=..., instructions=...)`. Replaces PF LLM nodes. |
| **Context Provider** | E.g. `AzureAISearchContextProvider` — injects RAG context into an agent. Replaces PF Embed Text + Vector Lookup nodes. |
| **SimilarityEvaluator** | From `azure-ai-evaluation`. Scores semantic similarity 1–5 between PF and MAF outputs. |

### Import Paths (MAF 1.0 GA)

```python
from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import HandoffBuilder  # multi-agent handoff
from agent_framework_azure_ai_search import AzureAISearchContextProvider
from azure.identity import DefaultAzureCredential
```

> **Package versions**: `agent-framework` and `agent-framework-foundry` are GA (1.0.1). `agent-framework-orchestrations` and `agent-framework-azure-ai-search` are still in preview (1.0.0b260409) and require `--pre` for pip install.

---

## Code Patterns

### Every sample follows this structure

1. **Define Executors** — one class per logical step, each with a `@handler` method.
2. **Build the Workflow** — connect executors via `WorkflowBuilder` and `.add_edge()`.
3. **Run** — `await workflow.run(input)`, read output from `result.get_outputs()`.

### Naming Conventions

- Executor class names: `<Purpose>Executor` (e.g. `InputExecutor`, `LLMExecutor`, `RouterExecutor`).
- Workflow names: descriptive PascalCase string (e.g. `"LinearWorkflow"`, `"RAGPipeline"`).
- Sample files: `NN_<pattern>.py` numbered by complexity (01–07).

### Message Construction

```python
# Correct (MAF 1.0 GA):
message = Message(role="user", contents=["Hello"])

# Incorrect (removed in 1.0):
message = Message(role="user", text="Hello")  # TypeError
```

### Workflow Output

Terminal executors must call `ctx.yield_output()`, not just `ctx.send_message()`:

```python
# Correct — yields a workflow output:
async def handle(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(text)
```

### Environment Variables

All credentials are read from `.env` via `load_dotenv()`. Never hard-code secrets. See `.env.example` for the full list:

- `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` (for all phase-2 samples and deployment)
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` (for parity evaluation only)
- `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_INDEX_NAME`, `AZURE_AI_SEARCH_API_KEY`
- `APPLICATIONINSIGHTS_CONNECTION_STRING` (tracing, Phase 4+)

---

## Modifying or Adding Samples

When adding a new sample to `phase-2-rebuild/`:

1. Number it sequentially after the last file (e.g. `08_<pattern>.py`).
2. Start with a docstring that names the Prompt Flow pattern being replaced.
3. Follow the three-step structure (Executors → Builder → Run).
4. Add the sample to the table in `phase-2-rebuild/README.md`.
5. If it introduces a new PF concept, add a row to `phase-1-audit/node-mapping.md`.

When editing existing samples:

- Keep the `load_dotenv()` call at the top, before any client instantiation.
- Preserve the `if __name__ == "__main__"` block so samples stay independently runnable.
- Use `asyncio.run(main())` as the entry point.

---

## Validation & Parity Checks

- **Single-row**: `python phase-3-validate/parity_check.py`
- **Batch (concurrent)**: `python phase-3-validate/parity_check_batch.py`
- Parity threshold: mean similarity ≥ **3.5** before proceeding to Phase 4.
- `SimilarityEvaluator` requires `model_config` with `azure_endpoint`, `api_key`, and `azure_deployment`.
- Correct kwargs: `evaluator(query=question, response=maf_answer, ground_truth=pf_answer)`.

---

## Deployment

- **Deploy script**: `phase-4-migrate-ops/4b-deployment/deploy.sh` (Azure ML Online Endpoints)
- **CI/CD quality gate**: `phase-4-migrate-ops/4c-cicd/evaluate.yml` (GitHub Actions)
- **Tracing**: Both `configure_azure_monitor()` and `configure_otel_providers()` must be called **before** any `workflow.run()`.

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: agent_framework` | Package not installed or RC conflict | `pip uninstall ... -y && pip install agent-framework>=1.0.1` |
| `401 Unauthorized` on Azure OpenAI | Missing/wrong API key or endpoint | Check `.env`; ensure endpoint ends with `/` |
| `workflow.run()` returns empty outputs | Terminal executor not calling `ctx.yield_output()` | Use `WorkflowContext[Never, T]` and call `ctx.yield_output()` |
| `TypeError` on `Message(text=...)` | Removed in 1.0 | Use `Message(role=..., contents=[...])` |
| Workflow hangs | Circular edge definition | Check `add_edge()` calls for cycles; set `max_iterations` |
| Low parity scores (< 2.0) | Wrong evaluator kwargs | Use `query=`, `response=`, `ground_truth=` |
| No traces in App Insights | Missing `configure_otel_providers()` or `configure_azure_monitor()` | Call both at startup, before `workflow.run()` |
| `WorkflowBuilder.build()` validation error | Missing start executor, type mismatch, duplicate IDs, or unreachable executor | Check `start_executor=`, edge types, and executor `id=` values |
| `/ask` returns 500 | `MAF_WORKFLOW_FILE` points at the wrong file, or the file does not define `workflow` | Point `MAF_WORKFLOW_FILE` at a valid workflow sample/module |
| Container App image pull error | ACR auth or tag mismatch | Verify `--registry-server`, `AcrPull` role, and image tag |

For the full list, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

---

## Common Pitfalls

1. **Mixing `--pre` and non-`--pre` installs** — Core MAF packages are GA; preview connectors (e.g. `agent-framework-copilotstudio`) still need `--pre` on a separate `pip install`. Never combine them in a single command.
2. **Foundry project endpoints require `FoundryChatClient`** — Foundry project endpoints (`*.services.ai.azure.com`) require `FoundryChatClient` from `agent_framework.foundry`.
3. **Fan-in missing a branch** — Every executor in `add_fan_out_edges()` must also appear in `add_fan_in_edges()`, or the aggregator fires early with a partial result.
4. **Fan-in handler receives `list[T]`, not `T`** — The aggregator executor's `@handler` parameter must be typed as `list[str]` (or `list[T]`), not a single `str`. The order matches the declaration order in `add_fan_in_edges()`.
5. **Condition functions receiving unexpected types** — Conditions receive the exact value passed to `ctx.send_message()`. Match on that value, not a transformed version. Use named functions, not lambdas, for readability and testability.
6. **Skipping Phase 3** — Always validate parity before migrating ops. Low-scoring outputs indicate unmigrated logic.
7. **Instantiating one client per agent** — Share a single `FoundryChatClient()` instance across multiple agents. Creating separate clients wastes connection resources. See `07_multi_agent.py` for the pattern.
8. **Forgetting `start_executor=`** — `WorkflowBuilder(...)` requires a `start_executor=` keyword argument. Also check for duplicate executor IDs, type mismatches on edges, and unreachable executors.
9. **Each executor needs a unique `id`** — The `id=` kwarg passed to the executor constructor must be unique within the workflow. Duplicates cause silent overwrites or runtime errors.
10. **Tool function docstrings drive agent behaviour** — When registering Python functions as agent tools via `tools=[fn]`, the agent uses the function's docstring to decide when and how to call it. Missing or vague docstrings lead to unreliable tool use.
11. **Use `HandoffBuilder` for multi-agent routing** — `07_multi_agent.py` uses `HandoffBuilder` from `agent-framework-orchestrations` which automatically generates handoff tools for each participant. This is cleaner than manual tagged-string routing with condition functions.
12. **Using `gpt_similarity` instead of `similarity`** — `SimilarityEvaluator` returns both keys. `gpt_similarity` is deprecated; always read from `similarity`.
13. **API keys in production Container Apps** — Use managed identity (`ManagedIdentityCredential`) and Key Vault secret references (`secretref:kv-*`) instead of inline API keys. See `phase-4-migrate-ops/4b-deployment/managed_identity.md`.
14. **`DefaultAzureCredential` for local + cloud portability** — Use `DefaultAzureCredential()` when code must run both locally (Azure CLI auth) and in Azure (managed identity). Avoid it in production-only paths where `ManagedIdentityCredential` is more predictable.

---

## External References

- [MAF 1.0 GA announcement](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/)
- [MAF Python API docs](https://learn.microsoft.com/en-us/agent-framework/)
- [MAF Workflows documentation](https://learn.microsoft.com/en-us/agent-framework/workflows/executors)
- [Azure AI Evaluation SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme)
- [MAF GitHub repository](https://github.com/microsoft/agent-framework)
- [MAF Discord community](https://discord.gg/b5zjErwbQM)
