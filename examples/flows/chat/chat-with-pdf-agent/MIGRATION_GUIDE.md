# Promptflow DAG Flow → Agent Framework Workflow Migration Guide

This document summarizes the key concepts and step-by-step process for migrating a promptflow DAG flow to a Microsoft Agent Framework `WorkflowBuilder`-based workflow, based on the hands-on migration of the `chat-with-pdf` project.

---

## Table of Contents

1. [Concept Mapping](#1-concept-mapping)
2. [Migration Steps](#2-migration-steps)
3. [Key Considerations](#3-key-considerations)
4. [Full Side-by-Side Example](#4-full-side-by-side-example)

---

## 1. Concept Mapping

| Promptflow Concept | Agent Framework Equivalent | Notes |
|---|---|---|
| `flow.dag.yaml` | `WorkflowBuilder` + `WorkflowAgent` | DAG topology defined in Python code instead of YAML |
| Node | `Executor` subclass | Each promptflow node maps to one `Executor` |
| Node's Python function | `@handler` method | Node logic lives in `Executor.handle()` |
| `${node_a.output}` input reference | `@dataclass` message type + `ctx.send_message()` | Data flows between nodes via typed dataclass messages |
| `inputs:` / `outputs:` | Entry JSON → `list[Message]`, terminal `ctx.yield_output()` | See detailed explanation below |
| Connection | Environment variables / `DefaultAzureCredential` | No built-in connection management; handle auth yourself |
| `setup_env` node | Plain function called before `create_workflow_agent()` | Initialization logic should not be an Executor |

---

## 2. Migration Steps

### Step 1: Analyze `flow.dag.yaml` and Map Out the DAG Topology

Extract node dependencies from the YAML. For the chat-with-pdf example:

```yaml
# Dependencies in flow.dag.yaml (via ${...} references)
setup_env
  ↓
download_tool  ←  inputs.pdf_url
  ↓
build_index_tool
  ↓               ↑ (build_index_tool.output)
rewrite_question_tool  ←  inputs.question, inputs.chat_history
  ↓
find_context_tool
  ↓
qna_tool  ←  inputs.chat_history
```

**Key point**: Identify nodes that are pure initialization (e.g., `setup_env`). Remove them from the DAG and call them as regular functions before creating the workflow.

### Step 2: Define Message Types for Each Edge

Define a `@dataclass` for each edge in the DAG, carrying all data required by the downstream node:

```python
from dataclasses import dataclass

@dataclass
class Downloaded:
    """Passed between download → build_index"""
    question: str
    pdf_url: str
    pdf_path: str
    chat_history: list

@dataclass
class Indexed:
    """Passed between build_index → rewrite_question"""
    question: str
    index_path: str
    chat_history: list

# ... define one for each edge
```

**Design principle**: Each message type must contain all fields the downstream node needs. In promptflow, any node can reference `${inputs.question}` to access the original input; in agent-framework, data must be explicitly forwarded through upstream Executors.

### Step 3: Convert Each Node to an Executor

Each promptflow node maps to an `Executor` subclass:

```python
from agent_framework import Executor, WorkflowContext, handler

class BuildIndexExecutor(Executor):
    @handler
    async def handle(self, msg: Downloaded, ctx: WorkflowContext[Indexed]) -> None:
        # Call existing business logic (reuse functions from promptflow directly)
        index_path = create_faiss_index(msg.pdf_path)
        # Send message to downstream executor
        await ctx.send_message(Indexed(
            question=msg.question,
            index_path=index_path,
            chat_history=msg.chat_history,
        ))
```

**Rules**:
- The `msg` parameter type on the `@handler` method determines what message the Executor receives
- The generic parameter of `WorkflowContext[OutputType]` determines what `send_message()` can send
- Intermediate nodes use `ctx.send_message()`; terminal nodes use `ctx.yield_output()`
- Existing business functions (download, create_faiss_index, etc.) can be reused as-is without modification

### Step 4: Handle the Start Executor's Special Input

`WorkflowAgent.run()` converts user input into `list[Message]`, so **the start Executor's handler signature must accept `list[Message]`** — not a custom dataclass:

```python
class DownloadExecutor(Executor):
    @handler
    async def handle(self, msg: list[Message], ctx: WorkflowContext[Downloaded]) -> None:
        # Extract text from the user-role message
        user_text = ""
        for m in msg:
            if m.role == "user":
                user_text = m.text or ""
                break
        # Parse JSON to get structured input
        data = json.loads(user_text)
        pdf_path = download(data["pdf_url"])
        await ctx.send_message(Downloaded(...))
```

On the caller side, serialize input as a JSON string:

```python
user_input = json.dumps({
    "question": question,
    "pdf_url": pdf_url,
    "chat_history": chat_history,
})
response = await agent.run(user_input)
```

### Step 5: Assemble the DAG with WorkflowBuilder

```python
from agent_framework import WorkflowBuilder, WorkflowAgent

def create_workflow_agent() -> WorkflowAgent:
    setup_env()  # Initialization (not an Executor)

    download_exec = DownloadExecutor(id="download")
    build_index_exec = BuildIndexExecutor(id="build_index")
    rewrite_exec = RewriteQuestionExecutor(id="rewrite_question")
    find_ctx_exec = FindContextExecutor(id="find_context")
    qna_exec = QnAExecutor(id="qna")

    workflow = (
        WorkflowBuilder(
            start_executor=download_exec,
            name="chat-with-pdf",
            description="Chat with PDF workflow",
        )
        .add_edge(download_exec, build_index_exec)
        .add_edge(build_index_exec, rewrite_exec)
        .add_edge(rewrite_exec, find_ctx_exec)
        .add_edge(find_ctx_exec, qna_exec)
        .build()
    )

    return WorkflowAgent(workflow=workflow, name="ChatWithPDF")
```

### Step 6: Extract Output from the Terminal Executor

The terminal Executor emits results via `ctx.yield_output()`:

```python
class QnAExecutor(Executor):
    @handler
    async def handle(self, msg: ContextFound, ctx: WorkflowContext[Never, ChatOutput]) -> None:
        # The second generic parameter of WorkflowContext is the yield_output type
        answer = qna(msg.prompt, msg.chat_history)
        await ctx.yield_output(ChatOutput(answer=answer, context=msg.context))
```

**Extracting the response**: The data from `yield_output()` is stored in `Message.raw_representation`:

```python
response = await agent.run(user_input)

for msg in response.messages:
    if isinstance(msg.raw_representation, ChatOutput):
        return {"answer": msg.raw_representation.answer, "context": msg.raw_representation.context}

# If you only need text, you can also use response.text (which is str(ChatOutput(...)))
```

### Step 7: Handle Authentication and Connections

Promptflow uses `connection` objects to manage credentials. In Agent Framework, you must handle this yourself:

```python
# Option 1: API Key (via environment variables)
init_params["api_key"] = os.environ["OPENAI_API_KEY"]

# Option 2: Azure CLI / Managed Identity (recommended)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)
init_params["azure_ad_token_provider"] = token_provider
```

---

## 3. Key Considerations

### 3.1 Calling Synchronous Functions from Async Handlers

The `@handler` method is `async def`, but existing promptflow node functions are typically synchronous. Calling synchronous functions directly from an async handler works (it blocks the current thread). For I/O-intensive operations, consider using `asyncio.to_thread()`:

```python
@handler
async def handle(self, msg: Downloaded, ctx: WorkflowContext[Indexed]) -> None:
    # Simple case: call directly (works, but blocks the event loop)
    index_path = create_faiss_index(msg.pdf_path)

    # Better approach: run in a thread
    index_path = await asyncio.to_thread(create_faiss_index, msg.pdf_path)
```

### 3.2 Data Forwarding — Carry-All vs Shared State

In promptflow, any node can reference original inputs via `${inputs.xxx}` or outputs from any completed node via `${other_node.output}`. In Agent Framework, an Executor can only receive messages from its direct upstream.

Strategies:
- **Carry-all** (recommended): Each dataclass message carries all fields needed by downstream nodes, including fields forwarded from the original input
- **Shared state**: Share data through closures or class attributes, but this sacrifices Executor testability

### 3.3 Branching / Parallel DAGs

If the promptflow DAG has branches (one node's output feeds multiple downstream nodes), use multiple `add_edge` calls:

```python
# A's output goes to both B and C
builder.add_edge(a_exec, b_exec)
builder.add_edge(a_exec, c_exec)
```

If a node needs to wait for results from multiple upstream nodes, you need multiple `@handler` methods accepting different message types, or redesign the merge logic.

### 3.4 `WorkflowContext` Generic Parameters

```python
WorkflowContext[SendType]              # Intermediate node: only uses send_message
WorkflowContext[SendType, OutputType]  # Can both send_message and yield_output
WorkflowContext[Never, OutputType]     # Terminal node: only uses yield_output (Never = no send)
```

### 3.5 Project Structure

Keep existing business logic code unchanged. Create a single new entry file to assemble the workflow:

```
chat-with-pdf-agent/
├── chat_with_pdf_agent.py      # New: Executor definitions + WorkflowBuilder assembly
├── chat_with_pdf/              # Copied from promptflow project as-is, no modifications
│   ├── download.py
│   ├── build_index.py
│   ├── find_context.py
│   ├── rewrite_question.py
│   ├── qna.py
│   └── utils/
├── .env                        # Environment variable configuration
└── requirements.txt            # agent-framework dependencies
```

---

## 4. Full Side-by-Side Example

### Promptflow Definition (flow.dag.yaml)

```yaml
nodes:
- name: download_tool
  type: python
  source:
    path: download_tool.py
  inputs:
    url: ${inputs.pdf_url}

- name: build_index_tool
  type: python
  source:
    path: build_index_tool.py
  inputs:
    pdf_path: ${download_tool.output}
```

### Agent Framework Equivalent

```python
# Message types
@dataclass
class Downloaded:
    pdf_path: str
    question: str
    chat_history: list

# Executor
class BuildIndexExecutor(Executor):
    @handler
    async def handle(self, msg: Downloaded, ctx: WorkflowContext[Indexed]) -> None:
        index_path = create_faiss_index(msg.pdf_path)
        await ctx.send_message(Indexed(question=msg.question, index_path=index_path, ...))

# Assembly
workflow = (
    WorkflowBuilder(start_executor=download_exec)
    .add_edge(download_exec, build_index_exec)
    .build()
)
agent = WorkflowAgent(workflow=workflow)
response = await agent.run(json.dumps({"pdf_url": "...", "question": "..."}))
```

---

## Migration Checklist

- [ ] Map out the full DAG topology from `flow.dag.yaml`
- [ ] Identify and remove pure initialization nodes (e.g., `setup_env`); call them as regular functions instead
- [ ] Define a `@dataclass` message type for each DAG edge, ensuring it carries all fields needed downstream
- [ ] Start Executor's `@handler` signature must accept `list[Message]`; parse with `json.loads()` inside
- [ ] Terminal Executor uses `ctx.yield_output()` with type annotation `WorkflowContext[Never, OutputType]`
- [ ] Intermediate Executors use `ctx.send_message()`
- [ ] Connect all Executors with `WorkflowBuilder.add_edge()` and call `.build()` to produce the workflow
- [ ] Wrap with `WorkflowAgent(workflow=workflow)`
- [ ] Extract results from `response.messages[*].raw_representation` to get the original dataclass object
- [ ] Handle authentication: API Key or `DefaultAzureCredential`
- [ ] Install dependencies: `agent-framework-core`, `agent-framework-azure-ai` (if using Azure OpenAI)

---

## Automated Migration with the Copilot Skill

A reusable Copilot skill has been built to automate this migration process. It encodes all the steps, patterns, and pitfalls described in this guide so you don't have to follow them manually.

### Location

The skill is located at `.github/skills/promptflow-to-agent-framework/SKILL.md` in this repository.

### How to Use

1. **Via slash command** — Type `/promptflow-to-agent-framework` in the GitHub Copilot chat panel, followed by the path to the promptflow flow directory:
   ```
   /promptflow-to-agent-framework examples/flows/chat/chat-with-pdf
   ```

2. **Via natural language** — Simply ask Copilot to migrate a promptflow flow to agent-framework. The skill will be auto-invoked when the request matches its trigger phrases:
   ```
   Migrate the promptflow flow in examples/flows/standard/web-classification to agent-framework workflow
   ```

3. **What it does** — The skill will:
   - Read and analyze the `flow.dag.yaml` in the specified directory
   - Map out the DAG topology and present it for confirmation
   - Create a new project directory with all necessary files
   - Define message dataclasses for each edge
   - Convert each node to an `Executor` subclass
   - Assemble the `WorkflowBuilder` DAG
   - Wire up the entry point with proper response extraction
   - Set up authentication handling
