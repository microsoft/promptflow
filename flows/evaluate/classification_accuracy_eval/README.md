# Classification Accuracy Evaluation

This is a flow illustrating how to evaluate the performance of a classification system. It involves comparing each prediction to the groundtruth and assigns a "Correct" or "Incorrect" grade, and aggregating the results to produce metrics such as accuracy, which reflects how good the system is at classifying the data.

## What you will learn

In this flow, you will learn
- how to compose a point based evaluation flow, where you can calculate point-wise metrics.
- the way to log metrics.

### Evaluate a classification flow
There are two ways to evaluate an classification flow.
* Run a classification flow and evaluation flow all together
    * step 1: create or clone an classification flow
    * step 2: select bulk test and fill in variants, then click on next
    * step 3: fill in test data, then click on next
    * step 3: when you are in evaluation setting page, use quotas for 'Sample evaluation flows'. Select 'Classification Accuracy Evaluation' from Sample evaluation flows, select the evaluation flow's inputs mapping from normal flow's inputs or outputs and click on next
    * step 4: review run settings and submit

* Run 'Classification Accuracy Evaluation' from an existing classification flow run
    * step 1: create a bulk test classification flow run and submit
    * step 2: click on 'View run history' to go to all submitted runs page and select a bulk test in bulk runs panel to go to details page
    * step 3: click on 'New evaluation', select one or more variants and the Classification Accuracy Evaluation from Sample evaluation flows. Then set connections, input mappings and submit

## Tools used in this flow
- Python Tool
