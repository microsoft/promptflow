<!-- 
bulk test
evaluate
add new evaluate runs
compare metrics
 -->

# Submit bulk test and evaluate a flow

To evaluate how well your flow performs with a large dataset, you can submit bulk test and use built-in evaluation methods in prompt flow. This document covers the following topics:

- [Submit a Bulk Test and Use a Built-in Evaluation Method](#submit-a-bulk-test-and-use-a-built-in-evaluation-method)
- [View the evaluation result and metrics](#view-the-evaluation-result-and-metrics)
- [Start A New Round of Evaluation](#start-a-new-round-of-evaluation)
- [Check Bulk Test History and Compare Metrics](#check-bulk-test-history-and-compare-metrics)
- [Understand the Built-in Evaluation Metrics](#understand-the-built-in-evaluation-metrics)
- [Ways to Improve Flow Performance](#ways-to-improve-flow-performance)
- [Conclusion](#conclusion)

You can quickly start testing and evaluating your flow by following this video tutorial:

[![develop_a_standard_flow](https://img.youtube.com/vi/5Khu_zmYMZk/0.jpg)](https://www.youtube.com/watch?v=5Khu_zmYMZk)

## Prerequisites

To run a bulk test and use an evaluation method, you need to have the following ready:

- A test dataset for bulk test. Your dataset should be in one of these formats: .csv, .tsv, .jsonl, or .parquet. Your data should also include headers that match the input names of your flow.
- An available runtime to run your bulk test. A runtime is a cloud-based resource that executes your flow and generates outputs. To learn more about runtime, please read [Runtime](./how-to-create-manage-runtime.md).

## Submit a Bulk Test and Use a Built-in Evaluation Method 

A bulk test allows you to run your flow with a large dataset and generate outputs for each data row. You can also choose an evaluation method to compare the output of your flow with certain criteria and goals. An evaluation method  **is a special type of flow**  that calculates metrics for your flow output based on different aspects. An evaluation run will be executed to calculate the metrics when submitted with the bulk test.

To start a bulk test with evaluation, you can click on the **"Bulk test"**  button on the top right corner of your flow page.

![Click "Bulk Test" button to test your flow with a larger set of data](../media/how-to-bulk-test-evaluate-flow/bulk-test-button.png)

To submit bulk test, you can select a dataset to test your flow with. You can also select an evaluation method to calculate metrics for your flow output. If you do not want to use an evaluation method, you can skip this step and run the bulk test without calculating any metrics. You can also start a new round of evaluation later.

First, select or upload a dataset that you want to test your flow with. An available runtime that can run your bulk test is also needed. You also give your bulk test a descriptive and recognizable name. After you finish the configuration, click on  **"Next"**  to continue.

![Select an available runtime and select a test dataset](../media/how-to-bulk-test-evaluate-flow/bulk-test-setting.png)

Second, you can decide to use an evaluation method to validate your flow performance either immediately or later. If you have already completed a bulk test, you can start a new round of evaluation with a different method or subset of variants.

- **Submit Bulk test without using evaluation method to calculate metrics:** You can click  **"Skip"** button to skip this step and run the bulk test without using any evaluation method to calculate metrics. In this way, this bulk test will only generate outputs for your dataset. You can check the outputs manually or export them for further analysis with other methods.

- **Submit Bulk test using evaluation method to calculate metrics:**  This option will run the bulk test and also evaluate the output using a method of your choice. A special designed evaluation method will run and calculate metrics for your flow output to validate the performance.

If you want to run bulk test with evaluation now, you can select an evaluation method from the dropdown box based on the description provided. After you selected an evaluation method, you can click on  **"View detail"**  button to see more information about the selected method, such as the metrics it generates and the connections and inputs it requires.

![Select built-in evaluation method from drop down box](../media/how-to-bulk-test-evaluate-flow/bulk-test-eval-selection.png)

In the  **"input mapping"**  section, you need to specify the sources of the input data that are needed for the evaluation method. The sources can be from the current flow output or from your test dataset, even if some columns in your dataset are not used by your flow. For example, if your evaluation method requires a _ground truth_ column, you need to provide it in your dataset and select it in this section.

You can also manually type in the source of the data column.

- If the data column is in your test dataset, then it is specified as **"data.[column\_name]".**
- If the data column is from your flow output, then it is specified as **"output.[output\_name]".**

![Define the required input columns for evaluation](../media/how-to-bulk-test-evaluate-flow/bulk-test-eval-input-mapping.png)

If an evaluation method uses Large Language Models (LLMs) to measure the performance of the flow response, you are required to set connections for the LLM nodes in the evaluation methods. Note that some evaluation methods require GPT-4 or GPT-3 to run. You must provide valid connections for these evaluation methods before using them.

![Configuration for connection for evaluation method](../media/how-to-bulk-test-evaluate-flow/bulk-test-eval-connection.png)

After you finish the input mapping, click on  **"Next"**  to review your settings and click on  **"Submit"**  to start the bulk test with evaluation.

![Review the setting of the bulk test submission](../media/how-to-bulk-test-evaluate-flow/bulk-test-review.png)

## View the evaluation result and metrics

In the bulk test detail page, you can check the status of the bulk test you submitted. In the  **"Evaluation History"** section, you can find the records of the evaluation for this bulk test. The link of the evaluation navigates to the snapshot of the evaluation run that executed for calculating the metrics.

![Check evaluation run](../media/how-to-bulk-test-evaluate-flow/bulk-test-detail.png)

When the evaluation run is completed, you can go to the **Outputs** tab in the bulk test detail page to check the outputs/responses generated by the flow with the dataset that you provided. You can also click **"Export"** to export and download the outputs in a .csv file.

You can  **select an evaluation run**  from the dropdown box and you will see additional columns appended at the end of the table showing the evaluation result for each row of data. In this screenshot, you can locate the result that is falsely predicted with the output column "grade".

![Check bulk test outputs](../media/how-to-bulk-test-evaluate-flow/bulk-test-detail-output.png)

To view the overall performance, you can click navigate to the **"Metrics"** tab, and you can see various metrics that indicate the quality of each variant.

![Check the overall performance in the metrics tab](../media/how-to-bulk-test-evaluate-flow/bulk-test-detail-metrics.png)

To learn more about the metrics calculated by the built-in evaluation methods, please navigate to [understand the built-in evaluation metrics](#understand-the-built-in-evaluation-metrics).

## Start A New Round of Evaluation

If you have already completed a bulk test, you can start another round of evaluation to submit a new evaluation run to calculate metrics for the outputs **without running your flow again**. This is helpful and can save your cost to re-run your flow when:

- you did not select an evaluation method to calculate the metrics when submitting the bulk test, and decide to do it now.
- you have already used evaluation method to calculate a metric. You can start another round of evaluation to calculate another metric.
- your evaluation run failed but your flow successfully generated outputs. You can submit your evaluation again.

You can click  **"New evaluation"**  to start another round of evaluation. The process is similar to that in submitting bulk test, except that you are asked to specify the output from which variants you would like to evaluate on in this new round.

![Start a new round of evaluation](../media/how-to-bulk-test-evaluate-flow/new-evaluation.gif)

After setting up the configuration, you can click  **"Submit"**  for this new round of evaluation. After submission, you will be able to see a new record in the "Evaluation History" Section.

![A new record of evaluation shows up in the evaluation history section](../media/how-to-bulk-test-evaluate-flow/bulk-test-detail-new-eval.png)

After the evaluation run completed, similarly, you can check the result of evaluation in the  **"Output"**  tab of the bulk test detail page. You need select the new evaluation run to view its result.

![Check new evaluation output](../media/how-to-bulk-test-evaluate-flow/bulk-test-detail-output-new-eval.png)

When muliple different evaluation runs are submitted for a bulk test, you can go to the **"Metrics"** tab of the bulk test detail page to compare all the metrics. 

## Check Bulk Test History and Compare Metrics
In some scenarios, you will modify your flow to improve its performance. You can submit multiple bulk tests to compare the performance of your flow with different versions. You can also compare the metrics calculated by different evaluation methods to see which one is more suitable for your flow.

To check the bulk test history of your flow, you can click on the **"Bulk test"** button on the top right corner of your flow page. You will see a list of bulk tests that you have submitted for this flow. 

![Check bulk test history](../media/how-to-bulk-test-evaluate-flow/bulk-test-history.png)

![Bulk test history list](../media/how-to-bulk-test-evaluate-flow/bulk-test-history-list.png)

You can click on each bulk test to check the detail. You can also select multiple bulk tests and click on the **"Compare Metrics"** to compare the metrics of these bulk tests.

![Compare metrics of multiple bulk tests](../media/how-to-bulk-test-evaluate-flow/bulk-test-compare.png)

## Understand the built-in evaluation metrics
In prompt flow, we provide multiple built-in evaluation methods to help you measure the performance of your flow output. Each evaluation method calculates different metrics. Now we provide nine built-in evaluation methods available, you can check the following table for a quick reference:
| Evaluation Method | Metrics  | Description | Connection Required | Required Input  | Score Value |
|---|---|---|---|---|---|
| Classification Accuracy Evaluation | Accuracy | Measures the performance of a classification system by comparing its outputs to groundtruth. | No | prediction, ground truth | in the range [0, 1]. |
| QnA Relevance Scores Pairwise Evaluation | Score, win/lose | Assesses the quality of answers generated by a question answering system. It involves assigning relevance scores to each answer based on how well it matches the user question, comparing different answers to a baseline answer, and aggregating the results to produce metrics such as averaged win rates and relevance scores. | Yes | question, answer (no ground truth or context)  | Score: 0-100, win/lose: 1/0 |
| QnA Groundedness Evaluation | Groundedness | Measures how grounded the model's predicted answers are in the input source. Even if LLM’s responses are true, if not verifiable against source, then is ungrounded.  | Yes | question, answer, context (no ground truth)  | 1 to 5, with 1 being the worst and 5 being the best. |
| QnA Ada Similarity Evaluation | Similarity | Measures similarity between user-provided ground truth answers and the model predicted answer.  | Yes | question, answer, ground truth (context not needed)  | in the range [0, 1]. |
| QnA Relevance Evaluation | Relevance | Measures how relevant the model's predicted answers are to the questions asked.  | Yes | question, answer, context (no ground truth)  | 1 to 5, with 1 being the worst and 5 being the best. |
| QnA Coherence Evaluation | Coherence  | Measures the quality of all sentences in a model's predicted answer and how they fit together naturally.  | Yes | question, answer (no ground truth or context)  | 1 to 5, with 1 being the worst and 5 being the best. |
| QnA Fluency Evaluation | Fluency  | Measures how grammatically and linguistically correct the model's predicted answer is.  | Yes | question, answer (no ground truth or context)  | 1 to 5, with 1 being the worst and 5 being the best |
| QnA f1 scores Evaluation | F1 score   | Measures the ratio of the number of shared words between the model prediction and the ground truth.  | No | question, answer, ground truth (context not needed)  | in the range [0, 1]. |
| QnA Ada Similarity Evaluation | Ada Similarity  | Computes sentence (document) level embeddings using Ada embeddings API for both ground truth and prediction. Then computes cosine similarity between them (1 floating point number)  | Yes | question, answer, ground truth (context not needed)  | in the range [0, 1]. |


## Ways to improve flow performance

After checking the [built-in metrics](#understand-the-built-in-evaluation-metrics) from the evaluation, you can try to improve your flow performance by:

- Check the output data to debug any potential failure of your flow.
- Modify your flow to improve its performance. This includes but not limited to:
  - Modify the prompt
  - Modify the system message
  - Modify parameters of the flow
  - Modify the flow logic

Prompt construction can be difficult. We provide a [Introduction to prompt engineering](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/concepts/prompt-engineering) to help you learn about the concept of constructing a prompt that can achieve your goal. You can also check the [Prompt engineering techniques](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/concepts/advanced-prompt-engineering?pivots=programming-language-chat-completions) to learn more about how to construct a prompt that can achieve your goal.

System message, sometimes referred to as a metaprompt or [system prompt](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/concepts/advanced-prompt-engineering?pivots=programming-language-completions#meta-prompts) that can be used to guide an AI system’s behavior and improve system performance. Read this document on [System message framework and template recommendations for Large Language Models(LLMs)](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/concepts/system-message) to learn about how to improve your flow performance with system message.

## Conclusion

In this document, you learned how to run a bulk test and use a built-in evaluation method to measure the quality of your flow output. You also learned how to view the evaluation result and metrics, and how to start a new round of evaluation with a different method or subset of variants. We hope this document helps you improve your flow performance and achieve your goals with prompt flow.