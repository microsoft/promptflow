# Develop an evaluation flow

Evaluation flows are special types of flows that assess how well the outputs of a flow align with specific criteria and goals.

In Prompt flow, you can customize or create your own evaluation flow tailored to your tasks and objectives, and then use in a bulk test as an evaluation method. This document covers the following topics:

- [Starting to develop an evaluation method](#starting-to-develop-an-evaluation-method)
  - [Customize Built-in Evaluation Method](#customize-built-in-evaluation-method-to-measure-the-performance-of-a-flow)
  - [Create New Evaluation Flow from Scratch](#create-new-evaluation-flow-from-scratch)
- [Understand Evaluation in Prompt flow](#understand-evaluation-in-prompt-flow)
  - [Inputs](#inputs)
  - [Outputs and Metrics Logging](#outputs-and-metrics)

## Starting to develop an evaluation method
There are two ways to develop your own evaluation methods:

- **Customize a Built-in Evaluation Flow:** Modify a built-in evaluation method based on your needs.
- **Create a New Evaluation Flow from Scratch:**  Develop a brand-new evaluation method from the ground up.

The process of customizing and creating evaluation methods is similar to that of a standard flow.

### Customize Built-in Evaluation Method to Measure the Performance of a Flow

Find the built-in evaluation methods by clicking the  **"Create"**  button on the homepage and navigating to the " Create from gallery -\> Evaluation tab. View more details about the evaluation method by clicking  **"View details"**.

![Create from gallery](../media/how-to-develop-an-evaluation-flow/create-from-gallery.png)

If you want to customize this evaluation method, you can click the **"Clone"** button.

![Customize Built-in Evaluation Method](../media/how-to-develop-an-evaluation-flow/customize-built-in.png)

By the name of the flow, you can see an **"evaluation"** tag, indicating you are building an evaluation flow. Similar to cloning a sample flow from gallery, you will be able to view and edit the flow and the codes and prompts of the evaluation method.

![evaluation tag](../media/how-to-develop-an-evaluation-flow/evaluation-tag.png)

Alternatively, you can customize a built-in evaluation method used in a bulk test by clicking the  **"Clone"**  icon when viewing its snapshot from the bulk test detail page.

![Clone from snapshot](../media/how-to-develop-an-evaluation-flow/clone-from-snapshot.gif)

### Create New Evaluation Flow from Scratch

To create your evaluation method from scratch, click the  **"Create"** button on the homepage and select  **"Evaluation"** as the flow type. You will enter the flow authoring page.

![create by type](../media/how-to-develop-an-evaluation-flow/create-by-type.png)

## Understand Evaluation in Prompt flow

In Prompt flow, a flow is a sequence of nodes that process an input and generate an output. Evaluation methods also take required inputs and produce corresponding outputs.

Some special features of evaluation methods are:

1. They need to handle outputs from flows that contain multiple variants.
2. They usually run after a flow being tested, so there is a field mapping process when submitting an evaluation.
3. They may have an aggregation node that calculates the overall performance of the flow being tested based on the individual scores.

We will introduce how the inputs and outputs should be defined in developing evaluation methods.

### Inputs

Different from a standard flow, evaluation methods run after a flow being tested, which may have multiple variants. Therefore, evaluation needs to distinguish the sources of the received flow output in a bulk test, including the data sample and variant the output is generated from.

To build an evaluation method that can be used in a bulk test, two additional inputs are required: line\_number and variant\_id(s).

- **line\_number:**  the index of the sample in the test dataset
- **variant\_id(s):** the variant id that indicates the source variant of the output

There are two types of evaluation methods based on how to process outputs from different variants:

- **Point-based evaluation method:** This type of evaluation flow calculates metrics based on the outputs from different variants **independently and separately.** "line\_number" and  **"variant\_id"**  are the required flow inputs. The receiving output of a flow is from a single variant. Therefore, the evaluation input "variant\_id" is a **string** indicating the source variant of the output.

| Field name | Type | Description | Examples |
| --- | --- | --- | --- |
| line\_number | int | The line number of the test data. | 0, 1, ... |
| **variant\_id** | **string** | **The variant name.** | **"variant\_0", "variant\_1", ...** |

- The built-in evaluation methods in the gallery are mostly this type of evaluation methods, except "QnA Relevance Scores Pairwise Evaluation".

- **Collection-based/Pair-wise evaluation method:**  This type of evaluation flow calculates metrics based on the outputs from different variants  **collectively.** "line\_number" and  **"variant\_ids"**  are the required flow inputs. This evaluation method receives a list of outputs of a flow from multiple variants. Therefore, the evaluation input "variant\_ids" is a **list of strings** indicating the source variants of the outputs. This type of evaluation method can process the outputs from multiple variant at a time, and calculate **relative metrics**, comparing to a baseline variant: variant\_0. This is useful when you want to know how other variants are performing compared to that of variant\_0 (baseline), allowing for the calculation of relative metrics.

| Field name | Type | Description | Examples |
| --- | --- | --- | --- |
| line\_number | int | The line number of the test data. | 0, 1, ... |
| **variant\_ids** | **List[string]** | **The variant name list.** | **["variant\_0", "variant\_1", ...]**|

See "QnA Relevance Scores Pairwise Evaluation" flow in "Create from gallery" for reference.

#### Input Mapping

In this context, the inputs are the subjects of evaluation, which are the outputs of a flow. Other inputs may also be required, such as ground truth, which may come from the test dataset you provided. Therefore, to run an evaluation, you need to indicate the sources of these required input test data. To do so, when submitting an evaluation, you will see an  **"input mapping"**  section.

- If the data source is from your test dataset, the source is indicated as "data.[ColumnName]"
- If the data source is from your flow output, the source is indicated as "output.[OutputName]"

![Input mapping section in bulk test submission process](../media/how-to-develop-an-evaluation-flow/bulk-test-eval-input-mapping.png)

To demonstrate the relationship of how the inputs and outputs are passed between flow and evaluation methods, here is a diagram showing the schema:

![Image](../media/how-to-develop-an-evaluation-flow/input-relationship.png)

Here is a diagram showing the example how data are passed between test dataset and flow outputs:

![Image](../media/how-to-develop-an-evaluation-flow/input-sample.png)

### Input description

To remind what inputs are needed to calculate metrics, you can add a description for each required input. The descriptions will be displayed when mapping the sources in bulk test submission.

![input description](../media/how-to-develop-an-evaluation-flow/input-description.png)

To add descriptions for each input, click "**Show description**" in the input section when developing your evaluation method. And you can click "Hide sedcription" to hide the description.

![Add description](../media/how-to-develop-an-evaluation-flow/add-description.png)

Then this description will be displayed to when using this evaluation method in bulk test submission.

### Outputs and Metrics

The outputs of an evaluation are the results that measure the performance of the flow being tested. The output usually contains metrics such as scores, and may also include text for reasoning and suggestions.

#### Instance-level Metrics —— Outputs

In Prompt flow, the flow processes each sample dataset one at a time and generates an output record. Similarly, in most evaluation cases, there will be a metric for each flow output, allowing you to check how the flow performs on each individual data input.

To record the score for each data sample, calculate the score for each output, and log the score  **as a flow output** by setting it in the output section. This is the same as defining a standard flow output.

![Image](../media/how-to-develop-an-evaluation-flow/eval-output.png)

When this evaluation method is used in a bulk test, the instance-level score can be viewed in the  **Output**  tab.

![Image](../media/how-to-develop-an-evaluation-flow/eval-output-bulk.png)

#### Metrics Logging and Aggregation Node

In addition, it is also important to provide an overall score for the run. You can check the  **"set as aggregation" ** of a Python node to turn it into  into a "reduce" node, allowing the node to take in the inputs  **as a list**  and process them in batch.

![Set as aggregation](../media/how-to-develop-an-evaluation-flow/set-as-aggregation.png)

In this way, you can calculate and process all the scores of each flow output and compute an overall result for each variant.

You can log metrics in an aggregation node using **Prompt flow_sdk.log_metrics()**. The metrics should be numerical (float/int). String type metrics logging is not supported.

See the following example for using the log_metric API:

```python
from typing import List
from promptflow import tool, log_metric

@tool
def calculate_accuracy(grades: List[str], variant_ids: List[str]):
    aggregate_grades = {}
    for index in range(len(grades)):
        grade = grades[index]
        variant_id = variant_ids[index]
        if variant_id not in aggregate_grades.keys():
            aggregate_grades[variant_id] = []
        aggregate_grades[variant_id].append(grade)

    # calculate accuracy for each variant
    for name, values in aggregate_grades.items():
        accuracy = round((values.count("Correct") / len(values)), 2)
        log_metric("accuracy", accuracy, variant_id=name)

    return aggregate_grades
```