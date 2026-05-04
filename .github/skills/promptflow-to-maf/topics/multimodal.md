# Multimodal Inputs (Images + Text)

> **Read this when** the source flow has image inputs, uses a `custom_llm` node with images, or targets a vision model (e.g., GPT-4V, GPT-4o vision).

## Key rule

When a flow has image inputs, you must build a `Message("user", [Content.from_uri(...), "text"])` and pass it to `Agent.run()`. **Joining image URLs into a plain string will NOT send the image to the model.**

The downstream Executor's `@handler` must accept `Message` (not `str`) and `WorkflowContext` must use `Message` as the send type.

## Multimodal Content Reference

`Agent.run()` accepts `AgentRunInputs = str | Content | Message | Sequence[str | Content | Message]`.

For multimodal inputs (images + text), use `Message` with mixed content:

| Input Type | How to Create |
|---|---|
| Image from URL | `Content.from_uri("https://example.com/img.png", media_type="image/png")` |
| Image from bytes | `Content.from_data(data=image_bytes, media_type="image/png")` |
| Image from base64 data URI | `Content.from_uri("data:image/png;base64,iVBOR...")` |
| Mixed image + text | `Message("user", [Content.from_uri(url, media_type="image/png"), "Describe this"])` |

## Prompt Flow Image Input Formats

Prompt Flow image inputs come in two formats — **both must be handled**:

- **Dict format** (from CLI): `{"data:image/png;url": "https://example.com/img.png"}` — extract the URL from the dict value
- **String format** (from YAML defaults): `"data:image/png;url: https://example.com/img.png"` — parse the URL after `url: `

For dicts, match the key against `data:image/...;url` and extract the value as the URL.
For strings, parse the URL after `url: ` using a regex.

For base64-encoded images, use `Content.from_data(data=image_bytes, media_type="image/...")`.

## Conversion checklist for multimodal nodes

1. Detect any input field whose value is a dict with key `data:image/*;url` or a string starting with `data:image/`.
2. Build a parser that handles both formats and yields a list of `Content | str` items.
3. In the InputExecutor, emit a `Message("user", contents)` instead of a plain string.
4. The downstream LLM Executor's `@handler` parameter must be `Message`, and the upstream `WorkflowContext[Message]` must declare `Message` as the send type.
5. Pass the `Message` directly to `Agent.run()` — do not stringify it.

See [examples/multimodal-chat.md](../examples/multimodal-chat.md) for a complete runnable example.
