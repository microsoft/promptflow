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

* __gpt_groundedness__ (against context): Measures how grounded the model's predicted answers are against the context. Even if LLM’s responses are true, if not verifiable against context, then such responses are considered ungrounded.

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
Prepare your Azure OpenAI resource follow this [instruction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal) and get your `api_key` if you don't have one.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/azure_openai.yml --set api_key=<your_api_key> api_base=<your_api_base>
```

## 1. Test flow/node
```bash
# test with default input value in flow.dag.yaml
pf flow test --flow .

# test with flow inputs
pf flow test --flow . --inputs metrics="ada_similarity,gpt_fluency,f1_score" question="what programming language is good for learning to code? " ground_truth="Python is good for learning to code." answer="Python" context="Python is the most picked language for learning to code."
```

## 2. Create flow run with multi line data and selected metrics
```bash
pf run create --flow . --data ./data.jsonl --column-mapping question='${data.question}' answer='${data.answer}' context='${data.context}' ground_truth='${data.ground_truth}' metrics='f1_score,gpt_groundedness' --stream
```
You can also skip providing `column-mapping` if provided data has same column name as the flow.
Reference [here](https://aka.ms/pf/column-mapping) for default behavior when `column-mapping` not provided in CLI.

## 3. Run and Evaluate your flow with this Q&A evaluation flow
After you develop your flow, you may want to run and evaluate it with this evaluation flow. 

Here we use the flow [basic_chat](../../chat/chat-basic/) as the flow to evaluate. It is a flow demonstrating how to create a chatbot with LLM.  The chatbot can remember previous interactions and use the conversation history to generate next message, given a question. 
### 3.1 Create a batch run of your flow
```bash
pf run create --flow ../../chat/chat-basic --data data.jsonl --column-mapping question='${data.question}' --name basic_chat_run --stream 
```
Please note that `column-mapping` is a mapping from flow input name to specified values. Please refer to [Use column mapping](https://aka.ms/pf/column-mapping) for more details. 

The flow run is named by specifying `--name basic_chat_run` in the above command. You can view the run details with its run name using the command:
```bash
pf run show-details -n basic_chat_run
```

### 3.2 Evaluate your flow
You can use this evaluation flow to measure the quality and safety of your flow responses.

After the chat flow run is finished, you can this evaluation flow to the run:
```bash
pf run create --flow . --data data.jsonl --column-mapping groundtruth='${data.ground_truth}' answer='${run.outputs.answer}' context='{${data.context}}' question='${data.question}' metrics='gpt_groundedness,f1_score'  --run basic_chat_run --stream --name evaluation_qa
```
Please note the flow run to be evaluated is specified with `--run basic_chat_run`. Also same as previous run, the evaluation run is named with `--name evaluation_qa`.
You can view the evaluation run details with:
```bash
pf run show-details -n evaluation_qa
pf run show-metrics -n evaluation_qa
```