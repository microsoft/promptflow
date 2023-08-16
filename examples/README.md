# Promptflow examples

[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![license: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](../LICENSE)

## Prerequisites

- Bootstrap your python env. 
  - e.g: create a new [conda](https://conda.io/projects/conda/en/latest/user-guide/getting-started.html) environment. `conda create -n pf-examples python=3.9`.
  - install required packages in python environment : `pip install -r requirements.txt`
    - show installed sdk: `pip show promptflow`


## Examples available

### Tutorials ([tutorials](tutorials))
| path | status | description |
------|--------|-------------
| [pipeline.ipynb](tutorials/flow-in-pipeline) | [![samples_flowinpipeline_pipeline](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml) | flow as component in pipeline |
| [quickstart-azure.ipynb](tutorials/get-started) | [![samples_getstarted_quickstartazure](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml) | get started - local to cloud |
| [quickstart.ipynb](tutorials/get-started) | [![samples_getstarted_quickstart](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml) | get started |
| [cloud-run-management.ipynb](tutorials/run-management) | [![samples_runmanagement_cloudrunmanagement](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml) | advanced flow run management |
| [deploy.md](tutorials/flow-deploy/deploy.md) | [![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml) | deploy flow as endpoint


### Flows ([flows](flows))

#### [Standard flows](flows/standard/) 

| path | status | description |
------|--------|-------------
| [basic](flows/standard/basic/flow.dag.yaml) | [![samples_flows_standard_basic](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml) | Basic standard flow |
| [basic-with-builtin-llm](flows/standard/basic-with-builtin-llm/flow.dag.yaml) | [![samples_flows_standard_basic_with_builtin_llm](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml) | Basic flow with builtin llm tool |
| [basic-with-connection](flows/standard/basic-with-connection/flow.dag.yaml) | [![samples_flows_standard_basic_with_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml) | Basic flow with custom connection |
| [flow-with-additional-includes](flows/standard/flow-with-additional-includes/flow.dag.yaml) | [![samples_flows_standard_flow_with_additional_includes](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml) | Flow with additional_includes |
| [flow-with-symlinks](flows/standard/flow-with-symlinks/flow.dag.yaml) | [![samples_flows_standard_flow_with_symlinks](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml) | Flow with symlinks |
| [intent-copilot](flows/standard/intent-copilot/flow.dag.yaml) | [![samples_flows_standard_intent_copilot](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml) | Intent-copilot |
| [summarizing-film-with-autogpt](flows/standard/summarizing-film-with-autogpt/flow.dag.yaml) | [![samples_flows_standard_summarizing_film_with_autogpt](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml) | Summarizing Film With AutoGPT |
| [web-classification](flows/standard/web-classification/flow.dag.yaml) | [![samples_flows_standard_web_classification](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml) | Web Classification |


#### [Evaluation flows](flows/evaluation/) 

| path | status | description |
------|--------|-------------
| [basic-eval](flows/evaluation/basic-eval/flow.dag.yaml) | [![samples_flows_evaluation_basic_eval](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_basic_eval.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_basic_eval.yml) | Basic Eval |
| [classification-accuracy-eval](flows/evaluation/classification-accuracy-eval/flow.dag.yaml) | [![samples_flows_evaluation_classification_accuracy_eval](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_classification_accuracy_eval.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_classification_accuracy_eval.yml) | Classification Accuracy Evaluation |


#### [Chat flows](flows/chat/)

| path | status | description |
------|--------|-------------
| [pf.ipynb](flows/chat/chat-with-pdf) | [![samples_flows_chat_chatwithpdf_pf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_pf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_pf.yml) | chat with pdf example |
| [basic-chat](flows/chat/basic-chat/flow.dag.yaml) | [![samples_flows_chat_basic_chat](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml) | Basic Chat |
| [chat-with-pdf](flows/chat/chat-with-pdf/flow.dag.yaml) | [![samples_flows_chat_chat_with_pdf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml) | Chat with PDF |
| [chat-with-wikipedia](flows/chat/chat-with-wikipedia/flow.dag.yaml) | [![samples_flows_chat_chat_with_wikipedia](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml) | Chat With Wikipedia |


### Connections ([connections](connections))

| path | status | description |
------|--------|-------------
| [connection.ipynb](connections) | [![samples_connections_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml) | connections sdk experience |


## Contributing

We welcome contributions and suggestions! Please see the [contributing guidelines](../CONTRIBUTING.md) for details.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). Please see the [code of conduct](../CODE_OF_CONDUCT.md) for details.

## Reference

* [Promptflow public documentation](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2)
* [Promptflow internal documentation](https://promptflow.azurewebsites.net/)