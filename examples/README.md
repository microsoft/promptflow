# Promptflow examples

[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![license: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](../LICENSE)

## Get started

**Install dependencies**

- Bootstrap your python environment. 
  - e.g: create a new [conda](https://conda.io/projects/conda/en/latest/user-guide/getting-started.html) environment. `conda create -n pf-examples python=3.9`.
  - install required packages in python environment : `pip install -r requirements.txt`
    - show installed sdk: `pip show promptflow`

**Quick start**

| path | status | description |
------|--------|-------------
| [quickstart.ipynb](tutorials/get-started) | [![samples_getstarted_quickstart](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml) | A quickstart tutorial to run a flow locally and evaluate it. |
| [quickstart-azure.ipynb](tutorials/get-started) | [![samples_getstarted_quickstartazure](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml) | A quickstart tutorial to run a flow in Azure AI and evaluate it. |


## CLI examples

### Tutorials ([tutorials](tutorials))

| path | status | description |
------|--------|-------------
| [chat-with-pdf](tutorials/e2e-development/chat-with-pdf.md) | [![samples_tutorials_e2e_development_chat_with_pdf](https://github.com/microsoft/promptflow/actions/workflows/samples_tutorials_e2e_development_chat_with_pdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_tutorials_e2e_development_chat_with_pdf.yml) |  Retrieval Augmented Generation (or RAG) has become a prevalent pattern to build intelligent application with Large Language Models (or LLMs) since it can infuse external knowledge into the model, which is not trained with those up-to-date or proprietary information |


### Flows ([flows](flows))

#### [Standard flows](flows/standard/) 

| path | status | description |
------|--------|-------------
| [basic](flows/standard/basic/README.md) | [![samples_flows_standard_basic](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic.yml) |  A basic standard flow using custom python tool that calls Azure OpenAI with connection info stored in environment variables |
| [basic-with-builtin-llm](flows/standard/basic-with-builtin-llm/README.md) | [![samples_flows_standard_basic_with_builtin_llm](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_builtin_llm.yml) |  A basic standard flow that calls Azure OpenAI with builtin llm tool |
| [basic-with-connection](flows/standard/basic-with-connection/README.md) | [![samples_flows_standard_basic_with_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_basic_with_connection.yml) |  A basic standard flow that using custom python tool calls Azure OpenAI with connection info stored in custom connection |
| [flow-with-additional-includes](flows/standard/flow-with-additional-includes/README.md) | [![samples_flows_standard_flow_with_additional_includes](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_additional_includes.yml) |  User sometimes need to reference some common files or folders, this sample demos how to solve the problem using additional_includes |
| [flow-with-symlinks](flows/standard/flow-with-symlinks/README.md) | [![samples_flows_standard_flow_with_symlinks](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_flow_with_symlinks.yml) |  User sometimes need to reference some common files or folders, this sample demos how to solve the problem using symlinks |
| [intent-copilot](flows/standard/intent-copilot/README.md) | [![samples_flows_standard_intent_copilot](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_intent_copilot.yml) |  This example shows how to create a flow from existing langchain code |
| [named-entity-recognition](flows/standard/named-entity-recognition/README.md) | [![samples_flows_standard_named_entity_recognition](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_named_entity_recognition.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_named_entity_recognition.yml) |  A flow that perform named entity recognition task |
| [summarizing-film-with-autogpt](flows/standard/summarizing-film-with-autogpt/README.md) | [![samples_flows_standard_summarizing_film_with_autogpt](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_summarizing_film_with_autogpt.yml) | This is a flow showcasing how to construct a AutoGPT flow to autonomously figures out how to apply the given functionsto solve the goal, which is film trivia that provides accurate and up-to-date information about movies, directors, actors, and more in this sample |
| [web-classification](flows/standard/web-classification/README.md) | [![samples_flows_standard_web_classification](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_standard_web_classification.yml) |  This is a flow demonstrating multi-class classification with LLM |


#### [Evaluation flows](flows/evaluation/)

| path | status | description |
------|--------|-------------
| [eval-basic](flows/evaluation/eval-basic/README.md) | [![samples_flows_evaluation_eval_basic](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_basic.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_basic.yml) |  This example shows how to create a basic evaluation flow |
| [eval-classification-accuracy](flows/evaluation/eval-classification-accuracy/README.md) | [![samples_flows_evaluation_eval_classification_accuracy](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_classification_accuracy.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_classification_accuracy.yml) |  This is a flow illustrating how to evaluate the performance of a classification system |
| [eval-entity-match-rate](flows/evaluation/eval-entity-match-rate/README.md) | [![samples_flows_evaluation_eval_entity_match_rate](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_entity_match_rate.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_entity_match_rate.yml) |  This is a flow evaluates: entity match rate |
| [eval-groundedness](flows/evaluation/eval-groundedness/README.md) | [![samples_flows_evaluation_eval_groundedness](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_groundedness.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_groundedness.yml) |  This is a flow leverage llm to eval groundedness: whether answer is stating facts that are all present in the given context |
| [eval-perceived-intelligence](flows/evaluation/eval-perceived-intelligence/README.md) | [![samples_flows_evaluation_eval_perceived_intelligence](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_perceived_intelligence.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_evaluation_eval_perceived_intelligence.yml) |  This is a flow leverage llm to eval percieved intelligence |


#### [Chat flows](flows/chat/)

| path | status | description |
------|--------|-------------
| [basic-chat](flows/chat/basic-chat/README.md) | [![samples_flows_chat_basic_chat](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_basic_chat.yml) |  This example shows how to create a basic chat flow |
| [chat-with-pdf](flows/chat/chat-with-pdf/README.md) | [![samples_flows_chat_chat_with_pdf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_pdf.yml) |  This is a simple flow that allow you to ask questions about the content of a PDF file and get answers |
| [chat-with-wikipedia](flows/chat/chat-with-wikipedia/README.md) | [![samples_flows_chat_chat_with_wikipedia](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chat_with_wikipedia.yml) |  This flow demonstrates how to create a chatbot that can remember previous interactions and use the conversation history to generate next message |


### Connections ([connections](connections))

| path | status | description |
------|--------|-------------
| [connections](connections/README.md) | [![samples_connections](https://github.com/microsoft/promptflow/actions/workflows/samples_connections.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_connections.yml) |  This folder contains example `YAML` files for creating `connection` using `pf` cli |


### Flow Deploy ([tutorials/flow-deploy/](tutorials/flow-deploy/))

| path | status | description |
------|--------|-------------
| [deploy.md](tutorials/flow-deploy/deploy.md) | | deploy flow as endpoint

## SDK examples

| path | status | description |
------|--------|-------------
| [quickstart.ipynb](tutorials/get-started) | [![samples_getstarted_quickstart](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstart.yml) | A quickstart tutorial to run a flow locally and evaluate it. |
| [quickstart-azure.ipynb](tutorials/get-started) | [![samples_getstarted_quickstartazure](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_getstarted_quickstartazure.yml) | A quickstart tutorial to run a flow in Azure AI and evaluate it. |
| [pipeline.ipynb](tutorials/flow-in-pipeline) | [![samples_flowinpipeline_pipeline](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flowinpipeline_pipeline.yml) | Use flow as component in pipeline |
| [cloud-run-management.ipynb](tutorials/run-management) | [![samples_runmanagement_cloudrunmanagement](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_runmanagement_cloudrunmanagement.yml) | Flow run management in Azure AI |
| [connection.ipynb](connections) | [![samples_connections_connection](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_connections_connection.yml) | Manage various types of connections using sdk |
| [chat-with-pdf-azure.ipynb](flows/chat/chat-with-pdf) | [![samples_flows_chat_chatwithpdf_chatwithpdfazure](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdfazure.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdfazure.yml) | A tutorial of chat-with-pdf flow that executes in Azure AI |
| [chat-with-pdf.ipynb](flows/chat/chat-with-pdf) | [![samples_flows_chat_chatwithpdf_chatwithpdf](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdf.yml/badge.svg?branch=main)](https://github.com/microsoft/promptflow/actions/workflows/samples_flows_chat_chatwithpdf_chatwithpdf.yml) | A tutorial of chat-with-pdf flow that allows user ask questions about the content of a PDF file and get answers |



## Contributing

We welcome contributions and suggestions! Please see the [contributing guidelines](../CONTRIBUTING.md) for details.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). Please see the [code of conduct](../CODE_OF_CONDUCT.md) for details.

## Reference

* [Promptflow documentation](https://microsoft.github.io/promptflow)