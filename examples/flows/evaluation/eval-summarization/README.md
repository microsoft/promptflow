# Summarization Evaluation

This flow implements a reference-free automatic abstractive summarization evaluation across four dimensions: fluency, coherence, consistency, relevance. Each dimension uses a prompt to score a generated summary against the source document from which it was generated. Each dimension's prompt has been meta-evaluated against the [SummEval benchmark](https://arxiv.org/abs/2007.12626) and produces state-of-the-art scores in terms of correlation to expert human judgements.

## Introduction

Provide a detailed description of the flow, including its components, inputs, outputs, and any dependencies. Explain how the flow works and what problem it solves. This section should give users a clear understanding of the flow's functionality and how it can be used. -- TODO remove this when done

Abstractive summarization evaluation is hard problem for which many previous automatic methods have performed poorly in-terms of correlation with human judgements. Furthermore, human expert created ground truths for summarization are hard to obtain and also hard to compare automatically to generated summaries. Thus there is a need for effective automatic reference-free summarization evaluation in which a generated summary is evaluated with respect to the document it was generated for.

This flow implements G-Eval for summarization evaluation that has been adopted from the [research paper](https://arxiv.org/abs/2303.16634) and associated [Github repository](https://github.com/nlpyang/geval). This method introduces a prompt based evaluation with GPT-4 for each of the 4 standard dimensions of summarization evaluation and shows state-of-the-art results from meta-evaluation against the [SummEval benchmark](https://arxiv.org/abs/2007.12626).

The 4 standard dimensions of summarization evaluation have been defined in prior research (see the SummEval paper for references) and a brief description of each is:

- Coherence - the collective quality of all sentences in the summary, scored on 1-5 scale
- Consistency - factual alignment between the summary and summarized source document, scored on a 1-5 scale
- Fluency - the quality of individual sentences of the summary, scored on a 1-3 scale (note this is an implementation difference compared to the original definition which uses a 1-5 scale)
- Relevance - selection of important content from the source document, scored on a 1-5 scale

This flow scores each summary along these dimensions and also aggregates each dimension as an average when run in batch mode.

The original G-Eval paper and repository has tuned prompts that refer to inputs as 'news-articles' (inline with the source data in the SummEval benchmark), we have modified the evaluation prompts provided in this flow to be more generic and agnostic to the domain of the source data being evaluated. These modified prompts have been meta-evaluated against the SummEval benchmark and show slightly lower performance to the original prompts (expected as they use more generic language) but still state-of-the-art performance compared to other automatic reference-free evaluation methods. Note that there is an assumption that meta-evaluation results against the SummEval benchmark will generalise to the domain of your data, if you have concerns about this please refer to the section on conducting your own meta-evaluation (TODO add link).

It is recommended to use this flow and it's prompts with only a GPT-4 model version, as the meta-evaluation results against the SummEval benchmark have been verified for only GPT-4. We recommend using [GPT-4 turbo](https://learn.microsoft.com/en-au/azure/ai-services/openai/concepts/models) as it provides a longer input context length, similar meta-evaluation performance to other GPT-4 models and cheaper token costs compared to other GPT-4 model versions. If this is unavailable, any other GPT-4 model would suffice and shows good meta-evaluation performance but you will need to be mindful of input token limits for each model version and the length of your documents and summaries that are being evaluated. Our meta-evaluation results with modified prompts and different GPT-4 models are shown in the table below.

<<TODO insert meta-eval table results>>

An important note regarding the implementation and use of this flow is that for each dimension, the evaluation prompt is run with temperature=2 and n=20, from which the final score is averaged across each trial. This is done as an approximation for token probabilities which are currently unavailable for GPT-4. This is run for each dimension for each summary being evaluated (ie. 20 LLM calls per summary), which may have cost considerations for your usecase.

<<TODO Bhavik add section on limitations in terms of gpt-4 bias favouring LLM summaries>>

<<TODO Bhavik add recommendation on using the scores outputted>>

<<TODO Bhavik add section on doing custom meta-evaluation and tuning prompts>>

## Tools Used in this Flow

List all the tools (functions) used in the flow. This can include both standard tools provided by prompt flow and any custom tools created specifically for the flow. Include a brief description of each tool and its purpose within the flow.  -- TODO remove this when done

Tools used in this flow：

- `python` tool the implements direct calls to GPT-4 (due to the need for using n=20, which is currently unavailable as a parameter in prompt flow LLM nodes) for each dimension's evaluation

## Pre-requisites

List any pre-requisites that are required to run the flow. This can include any specific versions of prompt flow or other dependencies. If there are any specific configurations or settings that need to be applied, make sure to mention them in this section. -- TODO remove this when done

Install Prompt Flow SDK and other dependencies in this folder:

```bash
pip install -r requirements.txt
```

## Getting Started
 
Provide step-by-step instructions on how to get started with the flow. This should include any necessary setup or configuration steps, such as installing dependencies or setting up connections. If there are specific requirements or prerequisites, make sure to mention them in this section.  -- TODO remove this when done

### Setup connection

Prepare your Azure Open AI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## Usage Examples

Include usage examples that demonstrate how to run the flow and provide input data. This can include command-line instructions or code snippets. Show users how to execute the flow and explain the expected output or results.   -- TODO remove this when done

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

## How to run Unit Tests

1. Make sure you already finished [Prerequisites](#pre-requisites)
1. Run the following commands

    ```bash
    pip install pytest
    python -m pytest tests
    ```

## Troubleshooting

If there are any known issues or troubleshooting tips related to the flow, include them in this section. Provide solutions or workarounds for common problems that users may encounter. This will help users troubleshoot issues on their own and reduce the need for support.   -- TODO remove this when done, or remove this section if not needed

## Contact

If you have any questions or issues related to this flow, please reach out to either:

- Bhavik Maneck [[Email](mailto:bhavikmaneck@microsoft.com) | [Linked-In](https://www.linkedin.com/in/bhavik-maneck/)]
- Kosuke Fujimoto [[Email](mailto:kofuji@microsoft.com) | [Linked-In](https://www.linkedin.com/in/kosuke-fuji/)]
