---
name: promptflow-to-maf
description: "Convert Prompt Flow flow definitions to Microsoft Agent Framework (MAF) workflows. Parses flow.dag.yaml, maps nodes to Executors, and generates runnable Python code using agent-framework 1.0.x. WHEN: convert promptflow, migrate promptflow, promptflow to MAF, promptflow to agent framework, convert flow.dag.yaml, migrate flow to MAF, convert PF flow, PF to agent-framework, convert DAG flow to workflow, migrate LLM flow."
license: MIT
metadata:
  author: Team
  version: "1.0.0"
---

# Prompt Flow → Microsoft Agent Framework Conversion

> Convert Prompt Flow `flow.dag.yaml` definitions into runnable MAF `WorkflowBuilder` Python code.

## Triggers

Activate this skill when the user wants to:
- Convert a Prompt Flow flow to Microsoft Agent Framework
- Migrate a `flow.dag.yaml` to MAF workflow code
- Rebuild a Prompt Flow application using `agent-framework`

## Rules

1. **Read the source flow first** — Always parse `flow.dag.yaml`, all referenced source files (`.jinja2`, `.py`), and `requirements.txt` before generating anything.
2. **One Executor per node** — Each Prompt Flow node becomes one `Executor` subclass with a `@handler` method.
3. **Preserve behaviour** — The MAF workflow must produce the same outputs for the same inputs as the original flow.
4. **Use GA packages** — `agent-framework>=1.0.1`, `agent-framework-openai>=1.0.1`. Use preview packages (`--pre`) only for orchestrations, Azure AI Search, or multi-agent features.
5. **Create output folder** — Place generated files in a sibling folder named `<original-folder>-maf/`.
6. **Copy user-defined Python packages** — If the flow imports from internal packages (e.g., `my_utils/`, helper modules), copy the entire package directory into the output folder. The MAF workflow imports directly from the local copy — no `sys.path` manipulation needed.
7. **Generate a test sample** — Always include a runnable `test_<name>.py` sample script.
8. **Never modify the original flow** — All output goes into the new folder.

---

## Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `agent-framework` | >=1.0.1 (GA) | Core: `Executor`, `WorkflowBuilder`, `WorkflowContext`, `Agent`, `@handler` |
| `agent-framework-openai` | >=1.0.1 (GA) | `OpenAIChatClient` — works for both OpenAI and Azure OpenAI |
| `agent-framework-foundry` | >=1.0.1 (GA) | `FoundryChatClient` — for Microsoft Foundry endpoints |
| `agent-framework-orchestrations` | preview | `HandoffBuilder` — for multi-agent handoffs |
| `agent-framework-azure-ai-search` | preview | `AzureAISearchContextProvider` — for RAG pipelines |
| `python-dotenv` | any | Load `.env` for credentials |

---

## Node Mapping Reference

Use this table to convert each Prompt Flow node type to its MAF equivalent:

| Prompt Flow Concept | MAF Equivalent |
|---|---|
| `flow.dag.yaml` (flow definition) | `WorkflowBuilder(name=..., start_executor=...).add_edge(...).build()` |
| Any node | `Executor` subclass with a `@handler` method |
| LLM node (`type: llm`) | `Agent(client=OpenAIChatClient(...), instructions=...)` inside an Executor |
| Python node (`type: python`) | Plain Python logic inside an `Executor` `@handler` |
| Prompt node (`.jinja2` template) | System prompt string passed to `Agent(instructions=...)`, or string formatting in `@handler` |
| Conditional / If node (`activate_config`) | `.add_edge(source, target, condition=fn)` |
| Parallel nodes (no shared deps) | `.add_fan_out_edges(source, [targetA, targetB])` |
| Merge / aggregate node | `.add_fan_in_edges([sourceA, sourceB], target)` |
| Embed Text + Vector Lookup + LLM (RAG) | `AzureAISearchContextProvider` via `context_providers=[...]` on `Agent` |
| Python tool node | Plain function passed to `Agent(tools=[fn1, fn2])` |
| Flow inputs | Type annotation on start Executor's `@handler` parameter (use `@dataclass` for multiple inputs) |
| Flow outputs (`is_chat_output`) | `await ctx.yield_output(value)` in the terminal Executor |
| Connections (credentials) | Environment variables + `OpenAIChatClient(azure_endpoint=..., api_key=...)` |
| `chat_history` input | Format into prompt string in an InputExecutor before passing to Agent |
| Variants | Separate Agent instances with different `instructions` strings |
| Multimodal input (image URL) | `Content.from_uri(url, media_type="image/png")` inside a `Message` |
| Multimodal input (base64 image) | `Content.from_data(data=bytes, media_type="image/png")` inside a `Message` |
| `custom_llm` node with images | Executor that builds a `Message("user", [Content.from_uri(...), text])` and passes it to `Agent.run()` |

---

## WorkflowContext Type Parameters

| Annotation | Behaviour |
|---|---|
| `WorkflowContext` | Side effects only — no output sent |
| `WorkflowContext[str]` | Sends a `str` downstream via `ctx.send_message()` |
| `WorkflowContext[Never, str]` | Yields a `str` as the final workflow output via `ctx.yield_output()` |
| `WorkflowContext[str, str]` | Both sends downstream AND yields a workflow output |

`Never` is imported from `typing_extensions`.

---

## Conversion Steps

### Phase 1: Audit the Prompt Flow

1. **Read `flow.dag.yaml`** — identify all inputs, outputs, nodes, their types, and edges (data references like `${node.output}`).
2. **Read source files** — open every `.jinja2` template and `.py` file referenced by nodes.
3. **Read `requirements.txt`** — note any extra dependencies.
4. **Map the graph** — draw the node dependency graph from `${...}` references. Identify:
   - Linear chains (A → B → C)
   - Parallel branches (A → B, A → C)
   - Conditional branches (`activate_config`)
   - Fan-in / aggregation points

### Phase 2: Generate MAF Code

5. **Create output folder** — `<original-folder>-maf/`
6. **Copy internal packages** — If nodes import from sibling Python packages (e.g., `from my_utils.helpers import ...`), copy those package directories into the output folder. Executors then import from the local copy directly (e.g., `from my_utils.helpers import build_index`). Do not rewrite working utility code — reuse it as-is.
7. **Create one Executor per node** following the mapping table above.
8. **Wire the workflow** using `WorkflowBuilder`:
   - `.add_edge(source, target)` for linear connections
   - `.add_edge(source, target, condition=fn)` for conditionals
   - `.add_fan_out_edges(source, [targets])` for parallel branches
   - `.add_fan_in_edges([sources], target)` for aggregation
9. **Handle LLM nodes**:
   - Extract system prompt from `.jinja2` template → `Agent(instructions="...")`
   - Use `OpenAIChatClient(azure_endpoint=..., model=..., api_key=...)` for Azure OpenAI
   - Use `FoundryChatClient(project_endpoint=..., model=..., credential=...)` for Foundry
   - `Agent.run()` returns an `AgentResponse` — extract text with `.text`
10. **Handle chat history** — format prior turns into a prompt string in an InputExecutor, not as raw message dicts.
11. **Handle multimodal / image inputs**:
    - Prompt Flow image references use two formats:
      - **Dict** (CLI input): `{"data:image/png;url": "https://..."}`
      - **String** (YAML default): `"data:image/png;url: https://..."`
    - For dicts, match the key against `data:image/...;url` and extract the value as the URL
    - For strings, parse the URL after `url: ` using a regex
    - Create `Content.from_uri(url, media_type="image/png")` for each image
    - For base64-encoded images, use `Content.from_data(data=image_bytes, media_type="image/...")`
    - Combine image `Content` objects and text strings into a `Message("user", [content1, text1, ...])`
    - Pass the `Message` (not a plain string) to `Agent.run()`
    - The downstream Executor's `@handler` must accept `Message` (not `str`) and `WorkflowContext` must use `Message` as the send type
12. **Handle Python tool nodes** — convert to plain functions and pass to `Agent(tools=[fn])`.

### Phase 3: Generate Supporting Files

13. **`requirements.txt`** — include only needed `agent-framework-*` packages.
14. **`.env.example`** — template with required environment variables (endpoint, key, model).
15. **`test_<name>.py`** — runnable sample script exercising single-turn and multi-turn (if applicable).
16. **`README.md`** — brief setup and run instructions (only if user requests documentation).

### Phase 4: Validate

17. **Create a virtual environment** and install dependencies.
18. **Run the test sample** to verify the workflow produces output.
19. **Fix any errors** — common issues:
    - `Agent.run()` returns `AgentResponse`, not `str` — use `.text`
    - `OpenAIChatClient` is the correct class (not `AzureOpenAIChatClient`)
    - `@handler` methods must be `async` and accept `(self, message, ctx)`

---

## LLM Client Selection

| Scenario | Client | Constructor |
|----------|--------|-------------|
| Azure OpenAI (API key) | `OpenAIChatClient` | `OpenAIChatClient(azure_endpoint=..., model=..., api_key=...)` |
| Azure OpenAI (Entra ID) | `OpenAIChatClient` | `OpenAIChatClient(azure_endpoint=..., model=..., credential=DefaultAzureCredential())` |
| OpenAI (direct) | `OpenAIChatClient` | `OpenAIChatClient(model=..., api_key=...)` |
| Microsoft Foundry | `FoundryChatClient` | `FoundryChatClient(project_endpoint=..., model=..., credential=DefaultAzureCredential())` |

> `OpenAIChatClient` auto-routes to Azure when `azure_endpoint` is provided. There is no separate `AzureOpenAIChatClient` class.

---

## Gotchas

1. **`Agent.run()` returns `AgentResponse`** — always use `response.text` to get the string output, then pass that to `ctx.yield_output()`.
2. **No `AzureOpenAIChatClient`** — use `OpenAIChatClient` with `azure_endpoint` for Azure routing.
3. **`@handler` message type must match upstream** — if the upstream executor sends a `str` via `ctx.send_message(str)`, the downstream `@handler` parameter must be typed as `str`.
4. **Chat history cannot be passed as `list[dict]` to `Agent.run()`** — format it into a single prompt string instead.
5. **Fan-in delivers `list[T]`** — the aggregator's `@handler` receives a list of all upstream messages.
6. **Condition functions receive the message** — `condition=fn` where `fn(message) -> bool`.
7. **Environment variables** — `OpenAIChatClient` can auto-read `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_MODEL` from env, but explicit constructor args are clearer.
8. **Multimodal inputs require `Message`, not `str`** — when a flow has image inputs (e.g., GPT-4V), you must build a `Message("user", [Content.from_uri(...), "text"])` and pass it to `Agent.run()`. Joining image URLs into a plain string will NOT send the image to the model.
9. **Internal package imports** — When a flow imports from sibling Python packages (e.g., `from my_utils.helpers import build_index`), copy the entire package directory into the MAF output folder. Do not rewrite utility code. The Executor files import directly from the local copy since they live in the same directory. Do not use `sys.path` hacks.
10. **Prompt Flow image format** — Prompt Flow image inputs come in two formats that must both be handled:
   - **Dict format** (from CLI): `{"data:image/png;url": "https://example.com/img.png"}` — extract the URL from the dict value
   - **String format** (from YAML defaults): `"data:image/png;url: https://example.com/img.png"` — parse the URL after `url: `
   - Both must be converted to `Content.from_uri(url, media_type="image/png")`

---

## Multimodal Content Reference

`Agent.run()` accepts `AgentRunInputs = str | Content | Message | Sequence[str | Content | Message]`.

For multimodal inputs (images + text), use `Message` with mixed content:

| Input Type | How to Create |
|---|---|
| Image from URL | `Content.from_uri("https://example.com/img.png", media_type="image/png")` |
| Image from bytes | `Content.from_data(data=image_bytes, media_type="image/png")` |
| Image from base64 data URI | `Content.from_uri("data:image/png;base64,iVBOR...")` |
| Mixed image + text | `Message("user", [Content.from_uri(url, media_type="image/png"), "Describe this"])` |

When an upstream Executor sends a `Message`, the downstream `@handler` parameter must be typed as `Message` (not `str`), and the `WorkflowContext` send type must be `Message`.

---

## Example: Linear Chat Flow

This converts a Prompt Flow with one LLM node and chat history:

```python
import asyncio
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from typing_extensions import Never
from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

@dataclass
class ChatInput:
    question: str
    chat_history: list | None = None

class InputExecutor(Executor):
    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        parts = []
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                parts.append(f"User: {turn['inputs']['question']}")
                parts.append(f"Assistant: {turn['outputs']['answer']}")
        parts.append(chat_input.question)
        await ctx.send_message("\n".join(parts))

class ChatExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ChatAgent",
            instructions="You are a helpful assistant.",
        )

    @handler
    async def call_llm(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(question)
        await ctx.yield_output(response.text)

_input = InputExecutor(id="input")
_chat = ChatExecutor(id="chat")

workflow = (
    WorkflowBuilder(name="BasicChatWorkflow", start_executor=_input)
    .add_edge(_input, _chat)
    .build()
)

async def main():
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print(result.get_outputs()[0])

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Example: Multimodal Chat Flow (Image + Text)

This converts a Prompt Flow with a `custom_llm` node that accepts image URLs (e.g., GPT-4V):

```python
import asyncio
import os
import re
from dataclasses import dataclass, field
from dotenv import load_dotenv
from typing_extensions import Never
from agent_framework import Agent, Content, Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# Matches Prompt Flow image key like "data:image/png;url"
_IMAGE_KEY_RE = re.compile(r"^data:image/[^;]+;url$")
# Matches Prompt Flow image string like "data:image/png;url: https://..."
_IMAGE_STR_RE = re.compile(r"^data:image/[^;]+;url:\s*(.+)$")


def _parse_question_parts(parts: list) -> list[Content | str]:
    """Convert Prompt Flow multimodal question parts to Content objects.

    Supports two formats:
    - dict: {"data:image/png;url": "https://example.com/img.png"}
    - string: "data:image/png;url: https://example.com/img.png"
    """
    contents: list[Content | str] = []
    for part in parts:
        if isinstance(part, dict):
            for key, url in part.items():
                if _IMAGE_KEY_RE.match(key):
                    contents.append(Content.from_uri(url, media_type="image/png"))
        elif isinstance(part, str):
            m = _IMAGE_STR_RE.match(part)
            if m:
                contents.append(Content.from_uri(m.group(1).strip(), media_type="image/png"))
            else:
                contents.append(part)
        else:
            contents.append(str(part))
    return contents


@dataclass
class ChatInput:
    question: list  # e.g. [{"data:image/png;url": "<url>"}, "How many colors?"]
    chat_history: list = field(default_factory=list)


class InputExecutor(Executor):
    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[Message]) -> None:
        contents: list[Content | str] = []
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                contents.append(f"User: {turn['inputs']['question']}")
                contents.append(f"Assistant: {turn['outputs']['answer']}")
        contents.extend(_parse_question_parts(chat_input.question))
        await ctx.send_message(Message("user", contents))


class ChatExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4v"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ChatImageAgent",
            instructions="You are a helpful assistant.",
        )

    @handler
    async def call_llm(self, prompt: Message, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)


_input = InputExecutor(id="input")
_chat = ChatExecutor(id="chat")

workflow = (
    WorkflowBuilder(name="ChatWithImageWorkflow", start_executor=_input)
    .add_edge(_input, _chat)
    .build()
)

async def main():
    result = await workflow.run(
        ChatInput(question=[
            "How many colors can you see?",
            {"data:image/png;url": "https://example.com/image.png"},
        ])
    )
    print(result.get_outputs()[0])

if __name__ == "__main__":
    asyncio.run(main())
```
