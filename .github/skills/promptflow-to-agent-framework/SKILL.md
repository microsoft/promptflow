---
name: promptflow-to-agent-framework
description: "Migrate promptflow DAG flows (flow.dag.yaml) to Microsoft Agent Framework WorkflowBuilder workflows. USE FOR: convert promptflow flow to agent-framework, migrate DAG flow, rewrite flow.dag.yaml as WorkflowBuilder, convert promptflow nodes to Executors, migrate promptflow to agent framework workflow. DO NOT USE FOR: creating new agent-framework projects from scratch, general agent-framework questions without a promptflow source."
argument-hint: "Path to the promptflow flow directory containing flow.dag.yaml"
---

# Promptflow → Agent Framework Migration Skill

Migrate a promptflow DAG flow (`flow.dag.yaml`) to a Microsoft Agent Framework `WorkflowBuilder` workflow with deterministic execution order.

## When to Use

- Converting an existing promptflow DAG flow to agent-framework
- The source project has a `flow.dag.yaml` defining nodes and edges
- You want to preserve the exact same execution order and logic

## Prerequisites

- `agent-framework-core` and `agent-framework-azure-ai` packages
- The source promptflow flow directory with `flow.dag.yaml` and node Python files

## Procedure

### Phase 1: Analyze the Promptflow Flow

1. Read `flow.dag.yaml` from the source directory
2. Extract the full DAG topology by tracing `${...}` input references
3. Identify:
   - **Flow inputs**: the `inputs:` section (types, defaults)
   - **Flow outputs**: the `outputs:` section (which node outputs they reference)
   - **Nodes**: each entry under `nodes:` (name, source file, inputs)
   - **Edges**: dependencies between nodes via `${node_name.output}` references
   - **Initialization nodes**: nodes like `setup_env` that only configure environment (no data output used downstream beyond a signal)
   - **Connection nodes**: nodes that reference a `connection:` input
4. Read each node's Python source file to understand its function signature, inputs, and return type
5. Present the DAG topology to the user for confirmation before proceeding

### Phase 2: Create the Agent Framework Project

1. Create a new directory alongside the original (e.g., `<flow-name>-agent/`)
2. Copy the business logic modules (utility packages, prompt templates, etc.) as-is — do NOT modify them
3. Create `requirements.txt`:
   ```
   agent-framework-core
   agent-framework-azure-ai
   python-dotenv
   # ... plus all dependencies from the original flow
   ```
4. Create `.env` with the required environment variables (API endpoints, model deployment names, etc.)

### Phase 3: Define Message Types

For each edge in the DAG, define a `@dataclass` message type. Follow these rules:

- Each dataclass carries **all fields** the downstream Executor needs (agent-framework Executors can only receive data from their direct upstream, unlike promptflow where any node can reference `${inputs.xxx}`)
- Fields that originate from flow inputs must be forwarded through intermediate dataclasses
- Name convention: past-tense verb or noun describing what happened (e.g., `Downloaded`, `Indexed`, `ContextFound`)
- Define a final output dataclass (e.g., `ChatOutput`) matching the flow's `outputs:` section

```python
from dataclasses import dataclass

@dataclass
class StepAOutput:
    """Passed from step_a → step_b"""
    result: str
    original_input: str  # forwarded from flow inputs
```

### Phase 4: Convert Nodes to Executors

Convert each promptflow node to an `Executor` subclass. Apply these rules:

#### Start Executor (first node in the DAG)
The handler **must** accept `list[Message]` because `WorkflowAgent.run()` converts user input to messages:

```python
from agent_framework import Executor, Message, WorkflowContext, handler

class StartExecutor(Executor):
    @handler
    async def handle(self, msg: list[Message], ctx: WorkflowContext[NextStepMessage]) -> None:
        user_text = ""
        for m in msg:
            if m.role == "user":
                user_text = m.text or ""
                break
        data = json.loads(user_text)
        # Call original business logic
        result = original_function(data["param"])
        await ctx.send_message(NextStepMessage(...))
```

#### Intermediate Executors
Accept the upstream dataclass, call business logic, send downstream dataclass:

```python
class MiddleExecutor(Executor):
    @handler
    async def handle(self, msg: PreviousOutput, ctx: WorkflowContext[NextOutput]) -> None:
        result = original_function(msg.field)
        await ctx.send_message(NextOutput(...))
```

#### Terminal Executor (last node)
Use `ctx.yield_output()` with `WorkflowContext[Never, OutputType]`:

```python
from typing_extensions import Never

class FinalExecutor(Executor):
    @handler
    async def handle(self, msg: PreviousOutput, ctx: WorkflowContext[Never, FinalOutput]) -> None:
        result = original_function(msg.field)
        await ctx.yield_output(FinalOutput(answer=result))
```

#### Initialization Nodes
Do NOT convert `setup_env`-style nodes to Executors. Convert them to plain functions called before workflow creation.

### Phase 5: Assemble the Workflow

```python
from agent_framework import WorkflowBuilder, WorkflowAgent

def create_workflow_agent(config=None):
    setup_env(config)  # initialization — not an Executor

    a = StartExecutor(id="step_a")
    b = MiddleExecutor(id="step_b")
    c = FinalExecutor(id="step_c")

    workflow = (
        WorkflowBuilder(
            start_executor=a,
            name="flow-name",
            description="Description of the workflow",
        )
        .add_edge(a, b)
        .add_edge(b, c)
        .build()
    )

    return WorkflowAgent(workflow=workflow, name="FlowName")
```

For branching DAGs (one node feeds multiple downstream):
```python
builder.add_edge(a, b)
builder.add_edge(a, c)  # a's output goes to both b and c
```

### Phase 6: Wire Up the Entry Point

Create the async entry function that:
1. Serializes input as JSON string
2. Calls `agent.run(user_input)`
3. Extracts the result from `response.messages[*].raw_representation`

```python
async def run_flow(input1, input2, **kwargs):
    agent = create_workflow_agent()
    user_input = json.dumps({"input1": input1, "input2": input2})
    response = await agent.run(user_input)

    # yield_output data is stored in Message.raw_representation
    if response.messages:
        for msg in response.messages:
            if isinstance(msg.raw_representation, FinalOutput):
                return {"answer": msg.raw_representation.answer}
        return {"answer": response.text}
    return {"answer": ""}
```

### Phase 7: Handle Authentication

Replace promptflow `connection` objects:

- **API Key**: Read from environment variables
- **Azure CLI / Managed Identity** (recommended):
  ```python
  from azure.identity import DefaultAzureCredential, get_bearer_token_provider
  credential = DefaultAzureCredential()
  token_provider = get_bearer_token_provider(
      credential, "https://cognitiveservices.azure.com/.default"
  )
  # Pass to AzureOpenAI client: azure_ad_token_provider=token_provider
  ```

### Phase 8: Test

1. Run the migrated script directly: `python <agent_file>.py`
2. Verify the output matches the original promptflow flow
3. Check that all nodes executed in the expected order

## Key Technical Details

### WorkflowContext Generic Parameters

| Signature | Usage |
|---|---|
| `WorkflowContext[SendType]` | Intermediate node — only `send_message()` |
| `WorkflowContext[SendType, OutputType]` | Can both `send_message()` and `yield_output()` |
| `WorkflowContext[Never, OutputType]` | Terminal node — only `yield_output()` |

### AgentResponse Output Extraction

`yield_output(MyDataclass(...))` is converted internally:
- The dataclass is stored in `Message.raw_representation`
- `response.text` contains `str(MyDataclass(...))` (the string representation)
- Always extract structured data from `raw_representation`, not from `text`

### Sync Functions in Async Handlers

Promptflow node functions are typically synchronous. They can be called directly from `async def handle()`. For I/O-heavy operations, wrap with `asyncio.to_thread()`:

```python
result = await asyncio.to_thread(heavy_sync_function, arg1, arg2)
```

## Reference Example

See the completed chat-with-pdf migration:
- Source: [examples/flows/chat/chat-with-pdf/flow.dag.yaml](../../../examples/flows/chat/chat-with-pdf/flow.dag.yaml)
- Migrated: [examples/flows/chat/chat-with-pdf-agent/chat_with_pdf_agent.py](../../../examples/flows/chat/chat-with-pdf-agent/chat_with_pdf_agent.py)
- Migration guide: [examples/flows/chat/chat-with-pdf-agent/MIGRATION_GUIDE.md](../../../examples/flows/chat/chat-with-pdf-agent/MIGRATION_GUIDE.md)

## Common Pitfalls

1. **Start Executor must accept `list[Message]`** — not a custom dataclass. `WorkflowAgent.run()` always wraps input as messages.
2. **Data must be forwarded explicitly** — unlike promptflow's `${inputs.xxx}`, agent-framework Executors only see their direct upstream message. Include all needed fields in each dataclass.
3. **Don't use `response.message.content`** — use `response.messages[*].raw_representation` to get structured output from `yield_output()`.
4. **Initialization nodes aren't Executors** — `setup_env`-style nodes should be plain functions called before building the workflow.
5. **No built-in connection management** — handle API keys and Azure credentials yourself via environment variables or `DefaultAzureCredential`.
