# Chat with MiniMax

This example demonstrates how to use [MiniMax](https://www.minimaxi.com/) as an LLM provider in prompt flow. MiniMax provides an OpenAI-compatible API, so it integrates seamlessly with prompt flow's existing OpenAI connection type.

## Prerequisites

- Install prompt flow: `pip install promptflow promptflow-tools`
- A MiniMax API key from [MiniMax Platform](https://platform.minimaxi.com/)

## Available Models

| Model | Description |
|-------|-------------|
| `MiniMax-M2.5` | General-purpose model with 204K context window |
| `MiniMax-M2.5-highspeed` | Faster variant optimized for lower latency |

## Setup

### Option 1: Using environment variable

```bash
export MINIMAX_API_KEY="your-api-key-here"
```

### Option 2: Using a prompt flow connection

Create a MiniMax connection using the OpenAI connection type with a custom base URL:

```bash
pf connection create -f ../../connections/minimax.yml --set api_key=<your-api-key>
```

## Run the example

### Run directly

```bash
export MINIMAX_API_KEY="your-api-key-here"
python flow.py
```

### Run as a flow

```bash
pf flow test --flow . --inputs question="What is Prompt flow?"
```

### Run with batch data

```bash
pf run create --flow . --data data.jsonl --column-mapping question='${data.question}' --stream
```

## Notes

- MiniMax's API is OpenAI-compatible, so it works with prompt flow's `OpenAIConnection` by setting `base_url` to `https://api.minimax.io/v1`.
- Temperature values are accepted in the range `[0.0, 1.0]`.
- The `MiniMax-M2.5` model supports a 204K context window, suitable for long-document analysis.
