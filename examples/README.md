# Promptflow examples

[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![license: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](../LICENSE)

## Prerequisites

- Bootstrap your python env. 
  - e.g: create a new [conda](https://conda.io/projects/conda/en/latest/user-guide/getting-started.html) environment. `conda create -n pf-examples python=3.9`.
  - install required packages in python environment : `pip install -r requirements.txt`
    - show installed sdk: `pip show promptflow`


## Examples available

### Getting started notebooks

| path | status | description |
------|--------|-------------
| [quickstart.ipynb](tutorials/get-started) | [![samples_getstarted_quickstart](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml) | get started |
| [quickstart-azure.ipynb](tutorials/get-started) | [![samples_getstarted_quickstartazure](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml) | get started - Azure AI |


### Flows ([flows](flows))

#### [Standard flows](flows/standard/) 

* Readmes

| path | status | description |
------|--------|-------------
| [basic](flows/standard/basic/README.md) | [![samples_flows_standard_basic](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml) |  A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables |
| [basic-with-builtin-llm](flows/standard/basic-with-builtin-llm/README.md) | [![samples_flows_standard_basic_with_builtin_llm](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml) |  A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables |
| [basic-with-connection](flows/standard/basic-with-connection/README.md) | [![samples_flows_standard_basic_with_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml) |  A basic standard flow that calls azure open ai with Azure OpenAI connection info stored in environment variables |
| [flow-with-additional-includes](flows/standard/flow-with-additional-includes/README.md) | [![samples_flows_standard_flow_with_additional_includes](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml) |  User sometimes need to reference some common files or folders on other top level folders |
| [flow-with-symlinks](flows/standard/flow-with-symlinks/README.md) | [![samples_flows_standard_flow_with_symlinks](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml) |  User sometimes need to reference some common files or folders on other top level folders |
| [intent-copilot](flows/standard/intent-copilot/README.md) | [![samples_flows_standard_intent_copilot](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml) |  This example shows how to create a flow from existing langchain code |
| [summarizing-film-with-autogpt](flows/standard/summarizing-film-with-autogpt/README.md) | [![samples_flows_standard_summarizing_film_with_autogpt](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml) | This is a flow showcasing how to construct a AutoGPT flow to autonomously figures out how to apply the given functionsto solve the goal, which is film trivia that provides accurate and up-to-date information about movies, directors, actors, and more in this sample |
| [web-classification](flows/standard/web-classification/README.md) | [![samples_flows_standard_web_classification](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml) |  This is a flow demonstrating multi-class classification with LLM |



#### [Evaluation flows](flows/evaluation/)

* Readmes

| path | status | description |
------|--------|-------------
| [basic-eval](flows/evaluation/basic-eval/README.md) | [![samples_flows_evaluation_basic_eval](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_basic_eval.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_basic_eval.yml) |  This example shows how to create a basic evaluation flow |
| [classification-accuracy-eval](flows/evaluation/classification-accuracy-eval/README.md) | [![samples_flows_evaluation_classification_accuracy_eval](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_classification_accuracy_eval.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_classification_accuracy_eval.yml) |  This is a flow illustrating how to evaluate the performance of a classification system |



#### [Chat flows](flows/chat/)

* Readmes

| path | status | description |
------|--------|-------------
| [basic-chat](flows/chat/basic-chat/README.md) | [![samples_flows_chat_basic_chat](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml) |  This example shows how to create a basic chat flow |
| [chat-with-pdf](flows/chat/chat-with-pdf/README.md) | [![samples_flows_chat_chat_with_pdf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml) |  This is a simple flow that allow you to ask questions about the content of a PDF file and get answers |
| [chat-with-wikipedia](flows/chat/chat-with-wikipedia/README.md) | [![samples_flows_chat_chat_with_wikipedia](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml) |  This is a companion flow to "Ask Wikipedia" |


* Notebooks

| path | status | description |
------|--------|-------------
| [chat-with-pdf.ipynb](flows/chat/chat-with-pdf) | [![samples_flows_chat_chatwithpdf_chatwithpdf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdf.yml) | chat with pdf example |



### Connections ([connections](connections))

* Readmes

| path | status | description |
------|--------|-------------
| [connections](connections/README.md) | [![samples_connections](https://github.com/microsoft/promptflow/actions/workflows/samples_connections.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_connections.yml) |  This repository contains example `YAML` files for creating `connection` using prompt-flow cli |


* Notebooks

| path | status | description |
------|--------|-------------
| [connection.ipynb](connections) | [![samples_connections_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml) | connections sdk experience |



### Tutorials ([tutorials](tutorials))

| path | status | description |
------|--------|-------------
| [pipeline.ipynb](tutorials/flow-in-pipeline) | [![samples_flowinpipeline_pipeline](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml) | flow as component in pipeline |
| [cloud-run-management.ipynb](tutorials/run-management) | [![samples_runmanagement_cloudrunmanagement](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml) | advanced flow run management |
| [deploy.md](tutorials/flow-deploy/deploy.md) | [![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml) | deploy flow as endpoint

## Contributing

We welcome contributions and suggestions! Please see the [contributing guidelines](../CONTRIBUTING.md) for details.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). Please see the [code of conduct](../CODE_OF_CONDUCT.md) for details.

## Reference

* [Promptflow public documentation](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2)
* [Promptflow internal documentation](https://promptflow.azurewebsites.net/)