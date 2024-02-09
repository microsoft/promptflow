# Summarization Evaluation

This example shows how to create a basic evaluation flow. 

Tools used in this flow：
- `python` tool

# G-Eval for Summarization

G-Eval for summarization has been adopted from the research paper <https://arxiv.org/abs/2303.16634> and associated Github repository <https://github.com/nlpyang/geval>. The code from the repository has been cleaned up and results from paper reproduced on the SummEval benchmark in the imported code has been put under `src/flows/evaluation/metrics/geval`.

The prompts for the original G-Eval SummEval benchmark have been modified to be more generic, as the original prompts refer to inputs as 'news articles'. The new prompts have been put under `prompts` and have been succesfully meta-evaluated. If any of the prompts are changed in future, they should be meta-evaluated using the code provided over the SummEval benchmark. Also see the section below on considerations for when to re-run meta-evaluation.

## Prerequisites

Install promptflow sdk and other dependencies in this folder:

```bash
pip install -r requirements.txt
```

## 0. Setup connection

Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## 1. Test flow with single line data

Testing flow/node:

```bash
# test with flow inputs
pf flow test --flow . --inputs document=ABC summary=ABC

# test node with inputs
pf flow test --flow . --node line_process --inputs document=ABC summary=ABC
```

## 2. create flow run with multi line data

There are two ways to evaluate an classification flow.

```bash
pf run create --flow . --data ./data.jsonl --column-mapping document='${data.document}' summary='${data.summary}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

## How to run unit tests

1. Make sure you already finished [Prerequisites](#prerequisites)
1. Run `pip install pytest`
1. Run `python -m pytest tests`
