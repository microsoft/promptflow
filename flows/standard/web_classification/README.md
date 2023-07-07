# Web Classification

This is a flow demonstrating multi-class classification with LLM. Given an url, it will classify the url into one web category with just a few shots, simple summarization and classification prompts.

## What you will learn

In this flow, you will learn
- how to compose a classification flow with LLM.
- how to feed few shots to LLM classifier.


## Getting Started

### 1 Create Azure OpenAI or OpenAI connection
Go to Prompt Flow "Connection" tab. Click on "Add" button, and start to set up your "AzureOpenAI" or "OpenAI" connection.

### 2 Configure the flow with your connection
Create or clone a new flow, go to the step need to configure connection. Select your connection from the connection drop-down box and fill in the configurations.

### 3 Run with classification evaluation flow
There are two ways to run with classification evaluation flow.
* Run an Web Classification flow and evaluation flow all together
    * step 1: clone an Web Classification flow
    * step 2: select bulk test and fill in variants, then click on next
    * step 3: fill in test data, then click on next
    * step 3: select an classification evaluation flow from Sample or Customer evaluation flows, select the evaluation flow's inputs mapping from normal flow's inputs or outputs and click on next
    * step 4: review run settings and submit

* Run 'Classification Accuracy Evaluation' from an existing Web Classification flow run
    * step 1: submit a bulk test Web Classification flow
    * step 2: click on 'View run history' to go to all submitted runs page and select a bulk test in bulk runs panel to go to details page
    * step 3: click on 'New evaluation', select one or more variants and the classification evaluation flow from Sample or Customer evaluation flows. Then set connections, input mappings and submit


## Tools used in this flow
- LLM Tool
- Python Tool
