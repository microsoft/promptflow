# Summarization Evaluation

This flow implements a reference-free automatic abstractive summarization evaluation across four dimensions: fluency, coherence, consistency, relevance. Each dimension uses a prompt with GPT-4 to score a generated summary against the source document from which it was generated. The implementation is based on the [G-Eval research paper](https://arxiv.org/abs/2303.16634).

## Introduction

### Background

Abstractive summarization evaluation is a hard problem for which many previous automatic methods have performed poorly in-terms of correlation with human judgements. Expert human created ground truths for summarization are hard to obtain and also hard to compare automatically to generated summaries. Prior research defines four dimensions to abstractive summary quality (each scored on a 1-5 Likert scale):
- Coherence - the collective quality of all sentences in the summary
- Consistency - factual alignment between the summary and source document
- Fluency - the quality of individual sentences of the summary
- Relevance - selection of the most important content from the source document

Thus it is possible to measure summary quality based on the inherent writing quality of the summary alone (in terms of coherence and fluency) and alignment between the summary and the source document (in terms of consistency and relevance). This affords the potential for a reference-free evaluation of abstractive summary generation.

This flow implements G-Eval for summarization evaluation that has been adopted from the [research paper](https://arxiv.org/abs/2303.16634) and associated [Github repository](https://github.com/nlpyang/geval). This method introduces a reference-free prompt based evaluation with GPT-4 for each of the 4 standard dimensions of summarization evaluation and shows state-of-the-art results in terms of correlation to human judgements based on meta-evaluation against the [SummEval benchmark](https://arxiv.org/abs/2007.12626).

## Tools Used in this Flow

Tools used in this flow：

- `python` tool the implements direct calls to GPT-4 (due to the need for using n=20, which is currently unavailable as a parameter in prompt flow LLM nodes) for each dimension's evaluation

## Pre-requisites

Install Prompt Flow SDK and other dependencies in this folder:

```bash
pip install -r requirements.txt
```

## Getting Started

### Setup connection

Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

Note that this evaluation flow is only validated to work with certain GPT-4 models versions (see meta-evaluation section).

## Usage Examples

This flow will evaluate a generated summary with respect to the source document it was generated from. Thus the flow requires two inputs, a document and a summary, as shown in the examples below. The output of the flow will be a score for each dimension of summarization evaluation (fluency, coherence, consistency, relevance) for each summary and if run in batch mode these dimensions will be averaged over each document and summary being evaluated.

### 1. Test flow with single line data

```bash
# test with flow inputs
pf flow test --flow . --inputs document=ABC summary=ABC
```

### 2. Create flow run with multi-line data

```bash
pf run create --flow . --data ./data.jsonl --column-mapping document='${data.document}' summary='${data.summary}' --stream
```

You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

## Implementation & Usage Details

The original G-Eval paper and repository has created prompts that refer to inputs as 'news-articles' (inline with the source data in the SummEval benchmark), we have modified the evaluation prompts provided in this flow to be more generic and agnostic to the domain of the source data being evaluated. Our implementation also includes an updated parser (extracting scores from 20 trial outputs) and other code improvements.

This flow scores generated summaries along each summarization evaluation dimension and also aggregates each dimension as an average when run in batch mode.

### Limitations

#### Cost considerations
An important note regarding the implementation and use of this flow is that for each dimension, the evaluation prompt is run using GPT-4 with temperature=2 and n=20, from which the final score is averaged across each trial. This is done as an approximation for token probabilities which are currently unavailable for GPT-4. This is run for each dimension for each summary being evaluated.

A rough estimate of the output tokens consumed by the flow per summary evaluation would be:
```
single_summary_eval_output_tokens = max_output_tokens*number_trials*number_dimensions = 5*20*4 = 400 output tokens
```

For input token estimation, if we assume a 500 word input doc and 50 word summary to evaluate, then the input tokens would be roughly (assuming 4 tokens per word):
```
(dimension input tokens = prompt tokens + source doc tokens + summary tokens)

consistency input tokens = 210 + 125 + 13 = 348 input tokens
fluency input tokens = 183 + 13 = 196 input tokens
relevance input tokens = 200 + 125 + 13 = 338 input tokens
coherence input tokens = 248 + 125 + 13 = 381 input tokens

total input tokens per doc/summary = 1263 input tokens
```
For a batch run of 100 documents, the price of using this flow could be estimated as:
```
total cost of summary eval flow = ((numb_summaries * input_tokens_per_summary / 1000) * gpt_4_cost_per_1k_output_tokens) + ((numb_summaries * output_tokens_per_summary / 1000) * gpt_4_cost_per_1k_output_tokens)

total cost of summary eval flow = ((100 * 1263 / 1000) * gpt_4_cost_per_1k_input_tokens) + ((100 * 400 / 1000) * gpt_4_cost_per_1k_output_tokens)
total cost of summary eval flow = (126.3 * gpt_4_cost_per_1k_input_tokens) + (40 * gpt_4_cost_per_1k_output_tokens)

Using GPT-4 8k model in East US region with USD pricing (as of 27/02/2024):
total cost of summary eval flow = (126.3 * $0.03) + (40 * $0.06) = $6.19 per 100 documents
```

Please substitute your own values for various variables to estimate the cost of running the evaluation flow on your data.

#### Scoring bias

The G-Eval research paper showed that G-Eval with GPT-4 has a bias to always scoring generated summaries (from GPT-35) higher than human written summaries, even when human reviewers would judge human written summaries to be better. In practice, we have observed this tendency of G-Eval with GPT-4 to produce a higher distribution of scores for each dimension. The mitigation we suggest for this is to sample a wider range at the bottom of the distribution (for each dimension) when conducting evaluation and error analysis.

### Meta-evaluation

The changes introduced in this flow's implementation (compared to the original G-Eval implementation from the research paper) have been meta-evaluated against the SummEval benchmark and show similar performance to the original implementation. As the prompts have been updated to be more generic we expect some change in performance to the original implementation which has tuned prompts to the SummEval benchmark (referring to news articles), but the updated implementation still shows state-of-the-art results compared to other metrics (see G-Eval paper for those results).

Meta-evaluation Spearman correlations between different experiments and human judgements in the SummEval benchmark:

| Dimension/Prompt       | Fluency | Consistency | Coherence | Relevance |
| ---------------------- | ------- | ----------- | --------- | --------- |
| GPT-4 0613 8k + original prompts in paper | 0.455  | 0.507      | 0.582    | 0.547    |
| GPT-4 0613 8k + updated prompts + original parser | 0.5079  | 0.5102      | 0.4998    | 0.4606    |
| GPT-4 0613 8k + updated prompts + updated parser | 0.5402  | 0.5215      | 0.5137    | 0.4897    |
| GPT-4 0613 32k + updated prompts + updated parser | 0.4985  | 0.4914      | 0.5038    | 0.4921    |

Note that GPT-4 Turbo has shown poor results when meta-evaluated and is currently not recommended to be used with this flow. It is recommended to use this flow and it's prompts with only the GPT-4 model versions listed above, as the meta-evaluation results have been verified for these model versions. 

There is an assumption that meta-evaluation results against the SummEval benchmark will generalise to the domain of your data, if you have concerns about this you should consider conducting your own meta-evaluation. This would include taking a significant sample of source documents and generated summaries and obtaining expert human judgements for each dimension of summarization evaluation (fluency, coherence, consistency, relevance). Then the prompts for each dimension should be tuned until sufficient correlation with human judgements are obtained.


## How to run Unit Tests

1. Make sure you already finished [Prerequisites](#pre-requisites)
1. Run the following commands

    ```bash
    pip install pytest
    python -m pytest tests
    ```

## Contact

If you have any questions or issues related to this flow, please reach out to either:

- Bhavik Maneck [[Email](mailto:bhavikmaneck@microsoft.com) | [Linked-In](https://www.linkedin.com/in/bhavik-maneck/)]
- Kosuke Fujimoto [[Email](mailto:kofuji@microsoft.com) | [Linked-In](https://www.linkedin.com/in/kosuke-fuji/)]
