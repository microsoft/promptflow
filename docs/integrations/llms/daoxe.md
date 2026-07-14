# Use DaoXE with prompt flow

[DaoXE](https://daoxe.com) is a multi-model multi-protocol API gateway. For prompt flow, use the **OpenAI connection** against DaoXE's OpenAI-compatible Chat Completions endpoint:

- Base URL: `https://daoxe.com/v1`
- Auth: API key from your DaoXE account
- Model: an **exact** model ID from your account catalog (`GET /v1/models`), not a static public list

DaoXE also exposes OpenAI Responses and Anthropic Messages (Claude protocol) for other clients. This page covers the OpenAI-compatible path that prompt flow's `OpenAIConnection` / prompty `type: openai` configuration already supports.

> DaoXE is **not available in mainland China**.

## Prerequisites

```sh
pip install promptflow promptflow-tools
```

Create a DaoXE API key at [daoxe.com](https://daoxe.com) and list models available to your key:

```sh
curl -sS https://daoxe.com/v1/models \
  -H "Authorization: Bearer $DAOXE_API_KEY"
```

## Create an OpenAI connection with DaoXE base URL

Reuse the generated `openai.yaml` from `pf flow init` (or any OpenAI connection YAML) and override `api_key` and `base_url`:

```sh
pf flow init --flow ./my_chatbot --type chat

pf connection create --file ./my_chatbot/openai.yaml \
  --set api_key=<your_daoxe_api_key> base_url=https://daoxe.com/v1 \
  --name open_ai_connection
```

In the flow's LLM / chat node, keep `connection: open_ai_connection` and set the model field (for example `model` / `deployment_name`, depending on the node schema) to an exact DaoXE model ID from your account.

## Environment variables

With `promptflow>=1.8.0` you can load an `OpenAIConnection` from the environment without writing a local connection DB entry:

```sh
export OPENAI_API_KEY=<your_daoxe_api_key>
export OPENAI_BASE_URL=https://daoxe.com/v1
```

| Connection Type | Field | Environment variable |
| --- | --- | --- |
| OpenAIConnection | api_key | `OPENAI_API_KEY` |
| OpenAIConnection | base_url | `OPENAI_BASE_URL` |

## Prompty configuration

```yaml
---
name: DaoXE Chat
description: Chat via DaoXE OpenAI-compatible endpoint
model:
  api: chat
  configuration:
    type: openai
    model: <exact-model-id-from-your-daoxe-account>
    api_key: ${env:OPENAI_API_KEY}
    base_url: ${env:OPENAI_BASE_URL}
  parameters:
    max_tokens: 256
    temperature: 0.2
inputs:
  question:
    type: string
sample:
  question: Say hello in one short sentence.
---
system:
You are a helpful assistant.

user:
{{question}}
```

Or override at load time:

```python
from promptflow.core import Prompty, OpenAIModelConfiguration

configuration = OpenAIModelConfiguration(
    model="<exact-model-id-from-your-daoxe-account>",
    base_url="https://daoxe.com/v1",
    api_key="${env:OPENAI_API_KEY}",
)
prompty = Prompty.load(
    source="path/to/chat.prompty",
    model={"configuration": configuration, "parameters": {"max_tokens": 256}},
)
```

## Smoke test with the OpenAI Python client

Before running a full flow, verify credentials and model ID:

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL", "https://daoxe.com/v1"),
)

resp = client.chat.completions.create(
    model=os.environ["DAOXE_MODEL"],  # exact ID from your catalog
    messages=[{"role": "user", "content": "Reply with the single word: pong"}],
    max_tokens=16,
)
print(resp.choices[0].message.content)
```

## Notes

- Prefer models that support the features your flow needs (tools, JSON mode, long context) as shown for your account.
- DaoXE model IDs and availability are account-scoped; always resolve them live.
- Multi-protocol note: prompt flow integration here is **Chat Completions** only. Anthropic Messages / Responses are for other stacks.
- Sample clients and setup notes: [DaoXE-AI](https://github.com/seven7763/DaoXE-AI)

## Disclosure

This page is contributed by a DaoXE maintainer.
