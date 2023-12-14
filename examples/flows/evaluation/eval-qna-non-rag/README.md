# Q&A Evaluation:

This is a flow evaluating the Q&A systems by leveraging Large Language Models (LLM) to measure the quality and safety of responses. Utilizing GPT and GPT embedding model to assist with measurements aims to achieve a high agreement with human evaluations compared to traditional mathematical measurements.

## Evaluation Metrics

The Q&A evaluation flow allows you to assess and evaluate your model with the LLM-assisted metrics and f1_score:


* __gpt_coherence__: Measures the quality of all sentences in a model's predicted answer and how they fit together naturally.

Coherence is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __gpt_relevance__: Measures how relevant the model's predicted answers are to the questions asked. 

Relevance metric is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __gpt_fluency__: Measures how grammatically and linguistically correct the model's predicted answer is.

Fluency is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best

* __gpt_similarity__: Measures similarity between user-provided ground truth answers and the model predicted answer.

Similarity is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best.

* __gpt_groundedness__ (against context)**: Measures how grounded the model's predicted answers are against the context. Even if LLM’s responses are true, if not verifiable against context, then such responses are considered ungrounded.

Groundedness metric is scored on a scale of 1 to 5, with 1 being the worst and 5 being the best. 

* __ada_similarity__: Measures the cosine similarity of ada embeddings of the model prediction and the ground truth.

ada_similarity is a value in the range [0, 1]. 

* __F1-score__: Compute the f1-Score based on the tokens in the predicted answer and the ground truth.

The f1-score evaluation flow allows you to determine the f1-score metric using number of common tokens between the normalized version of the ground truth and the predicted answer.

 F1-score is a value in the range [0, 1]. 

## Tools used in this flow
- `Python` tool
- `LLM` tool
- `Embedding` tool

## 0. Setup connection
Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## 1. Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs metrics="ada_similarity,gpt_fluency,f1_score" question="what programming language is good for learning to code? " ground_truth="Python is good for learning to code." answer="Python" context="Python is the most picked lanaguge for learning to code"
```

## 2. Create flow run with multi line data and selected metrics
```bash
pf run create --flow . --data ./data.jsonl --column-mapping question='${data.question}' answer='${data.answer}' context='${data.context}' ground_truth='${data.ground_truth}' metrics='f1_score,gpt_groundedness' --stream
```
You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.