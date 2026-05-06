# Node Variants (`node_variants` / `use_variants`)

> **Read this when** the source `flow.dag.yaml` contains a `node_variants:` block, or any node has `use_variants: true`.

## What `node_variants` means in Prompt Flow

`node_variants` lets a single node slot have **multiple alternative configurations** (different prompts, model parameters, connections, even different node bodies). At run time PF picks **exactly one** variant per node — the one named by `--variant '${node.variant_x}'`, or the node's `default_variant_id` if nothing is specified. Other variants do **not** execute.

```yaml
- name: summarize_text_content
  use_variants: true            # ← node body is in node_variants below

node_variants:
  summarize_text_content:
    default_variant_id: variant_0
    variants:
      variant_0: { node: { type: llm, ... temperature: 0.2, ... } }
      variant_1: { node: { type: llm, ... temperature: 0.3, ... } }
```

So conceptually a variant is a **swap-in node body**, and only one is "live" per run.

## MAF has no `variants` primitive

Microsoft Agent Framework has no first-class concept of "node variants". You implement the same behavior with plain Python: build the workflow with whichever configuration the caller asked for. Two patterns cover every real flow.

---

## Pattern A — Single Executor + `variant` parameter (default)

Use when the variants differ **only** in:
- Prompt text (different `.jinja2` content)
- LLM parameters (`temperature`, `max_tokens`, `top_p`, ...)
- Model / deployment name
- Connection (endpoint / api key)

This covers the vast majority of real Prompt Flow variants. The Executor stays one class; the variant just selects from a config dict.

```python
VARIANT_INSTRUCTIONS = {
    "variant_0": "You are an assistant... return only the final answer.",
    "variant_1": "You are an assistant... think step by step. Return JSON.",
    "variant_2": "You are an assistant... here are 5 examples: ...",
}

# Optional: per-variant LLM parameters
VARIANT_OPTIONS = {
    "variant_0": {"temperature": 0.2, "max_tokens": 128},
    "variant_1": {"temperature": 0.3, "max_tokens": 256},
    "variant_2": {"temperature": 0.3, "max_tokens": 256},
}


class ChatExecutor(Executor):
    def __init__(self, variant: str = "variant_0", **kwargs):
        super().__init__(**kwargs)
        self._opts = VARIANT_OPTIONS[variant]
        self._agent = Agent(
            client=OpenAIChatClient(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
            ),
            instructions=VARIANT_INSTRUCTIONS[variant],
        )

    @handler
    async def call_llm(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        response = await self._agent.run(prompt, **self._opts)
        await ctx.send_message(response.text)


def create_workflow(variant: str = "variant_0"):
    _input = InputExecutor(id="input")
    _chat = ChatExecutor(id="chat", variant=variant)
    _extract = ExtractResultExecutor(id="extract_result")
    return (
        WorkflowBuilder(name="ChatMathVariantWorkflow", start_executor=_input)
        .add_edge(_input, _chat)
        .add_edge(_chat, _extract)
        .build()
    )
```

Mapping back to PF concepts:

| Prompt Flow | MAF (Pattern A) |
|---|---|
| `node_variants:` block | `VARIANT_INSTRUCTIONS` (+ optional `VARIANT_OPTIONS`) dict |
| `default_variant_id: variant_0` | `def create_workflow(variant: str = "variant_0")` default |
| `use_variants: true` node | Single Executor that takes a `variant` arg |
| `pf run --variant '${node.variant_1}'` | `create_workflow(variant="variant_1")` (or env var) |

A complete reference is [chat-math-variant-maf](../../../../examples/flows/chat/chat-math-variant-maf/workflow.py).

---

## Pattern B — One Executor per variant

Use **only** when variants differ in something more than prompt/parameters:

1. **Different node `type`** — e.g. `variant_0` is `type: llm`, `variant_1` is `type: python`. The clients, dependencies, and error-handling diverge enough that a single class becomes a tangle of `if variant == ...`.
2. **Different tools / `context_providers`** — e.g. `variant_1` adds an Azure AI Search retriever or extra Python tools to the Agent. Tool sets are decided at construction, not per-call.
3. **Different input/output schema** — `@handler` signatures are strongly typed, and Pattern A can't change them per variant.
4. **Different upstream/downstream connections** — e.g. `variant_1` needs an extra preprocessing step. The graph itself changes, so the `WorkflowBuilder` must branch (whether or not the Executor splits is secondary).
5. **A/B comparison in a single run** — you want to fan out to all variants at once and compare. PF can't do this natively, but MAF can with `add_fan_out_edges` / `add_fan_in_edges`.

Skeleton:

```python
class Variant0Executor(Executor): ...
class Variant1Executor(Executor): ...     # different tools, schema, or type

EXECUTORS = {"variant_0": Variant0Executor, "variant_1": Variant1Executor}


def create_workflow(variant: str = "variant_0"):
    _input = InputExecutor(id="input")
    _chat = EXECUTORS[variant](id="chat")
    _post = PostExecutor(id="post")

    builder = WorkflowBuilder(name="...", start_executor=_input).add_edge(_input, _chat)

    # Variant-specific upstream/downstream wiring (case 4 above)
    if variant == "variant_1":
        _retrieve = RetrieveExecutor(id="retrieve")
        builder = builder.add_edge(_input, _retrieve).add_edge(_retrieve, _chat)

    return builder.add_edge(_chat, _post).build()
```

A/B fan-out variant of Pattern B (run all variants for evaluation):

```python
def create_ab_workflow():
    _input = InputExecutor(id="input")
    branches = [Variant0Executor(id="v0"), Variant1Executor(id="v1"), Variant2Executor(id="v2")]
    _compare = CompareExecutor(id="compare")
    return (
        WorkflowBuilder(name="ABCompare", start_executor=_input)
        .add_fan_out_edges(_input, branches)
        .add_fan_in_edges(branches, _compare)
        .build()
    )
```

---

## Decision tree

```
Variants differ in...
├── prompt text only                          → Pattern A
├── prompt + LLM params (temperature, etc.)   → Pattern A (+ VARIANT_OPTIONS dict)
├── connection / model / deployment           → Pattern A (+ per-variant client kwargs)
├── node type (llm vs python vs custom tool)  → Pattern B
├── tool set / context_providers              → Pattern B
├── input/output schema (handler signature)   → Pattern B
├── upstream/downstream edges                 → builder branches (Pattern A or B)
└── must compare all variants in one run      → Pattern B + fan_out / fan_in
```

When in doubt, start with **Pattern A**. It is closer to the PF mental model ("one node slot, swap-in config") and produces the smallest diff. Promote to Pattern B only when one of the conditions above forces it.

---

## Multiple nodes with variants

PF allows `node_variants` on several nodes; a single `pf run` picks one variant per node (others fall back to their `default_variant_id`). Keep the same shape in MAF — accept a dict so callers can mix and match without an exponential class explosion:

```python
def create_workflow(variants: dict[str, str] | None = None):
    variants = variants or {}
    _summarize = SummarizeExecutor(
        id="summarize_text_content",
        variant=variants.get("summarize_text_content", "variant_0"),
    )
    _classify = ClassifyExecutor(
        id="classify_with_llm",
        variant=variants.get("classify_with_llm", "variant_0"),
    )
    ...
```

Caller:

```python
wf = create_workflow(variants={"summarize_text_content": "variant_1"})
```

This is the direct equivalent of `pf run --variant '${summarize_text_content.variant_1}'`, and it scales: two nodes with 3 and 2 variants respectively stay 2 Executor classes (Pattern A) instead of becoming 6 (Pattern B).

---

## Output rules (in addition to the Core Rules in `SKILL.md`)

- Always preserve every variant's prompt **verbatim** (Core Rule 2). Each variant's `.jinja2` becomes its own constant (`VARIANT_0_INSTRUCTIONS`, etc.) — do not merge or deduplicate prompt text even if variants share large prefixes.
- The default value of the `variant` parameter must equal `default_variant_id` from the YAML.
- If only one variant exists in `node_variants` (sometimes used as a poor-man's prompt holder), collapse it to a plain Executor with no `variant` parameter — there is nothing to switch.
- Document the variant switch in the generated `.env.example` (e.g., `CHAT_VARIANT=variant_0`) and the `test_<name>.py` sample.
