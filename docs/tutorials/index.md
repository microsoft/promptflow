# Tutorials

This section contains a collection of flow samples and step-by-step tutorials.

|Category|<div style="width:250px">Sample</div>|Description|
|--|--|--|
|Tracing|[Tracing](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/tracing/README.md)| Prompt flow provides the tracing feature to capture and visualize the internal execution details for all flows|
|Tracing|[Tracing with llm application](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/tracing/llm/trace-llm.ipynb)|Tracing LLM application|
|Tracing|[Tracing with autogen](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/tracing/autogen-groupchat/trace-autogen-groupchat.ipynb)|Tracing LLM calls in autogen group chat application|
|Tracing|[Tracing with langchain apps](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/tracing/langchain/trace-langchain.ipynb)|Tracing LLM calls in langchain application|
|Tracing|[Tracing with custom opentelemetry collector](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/tracing/custom-otlp-collector/otlp-trace-collector.ipynb)|A tutorial on how to levarage custom OTLP collector.|
|Prompty|[Getting started with prompty](https://github.com/microsoft/promptflow/blob/main/examples/prompty/basic/prompty-quickstart.ipynb)|A quickstart tutorial to run a prompty and evaluate it.|
|Prompty|[Chat with prompty](https://github.com/microsoft/promptflow/blob/main/examples/prompty/chat-basic/chat-with-prompty.ipynb)|A quickstart tutorial to run a chat prompty and evaluate it.|
|Prompty|[Prompty output format](https://github.com/microsoft/promptflow/blob/main/examples/prompty/format-output/prompty-output-format.ipynb)||
|Flow|[Getting started with flex flow](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/basic/flex-flow-quickstart.ipynb)|A quickstart tutorial to run a flex flow and evaluate it.|
|Flow|[Chat with class based flex flow](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/chat-basic/chat-with-class-based-flow.ipynb)|A quickstart tutorial to run a class based flex flow and evaluate it.|
|Flow|[Stream chat with async flex flow](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/chat-async-stream/chat-stream-with-async-flex-flow.ipynb)|A quickstart tutorial to run a class based flex flow in stream mode and evaluate it.|
|Flow|[Stream chat with flex flow](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/chat-stream/chat-stream-with-flex-flow.ipynb)|A quickstart tutorial to run a class based flex flow in stream mode and evaluate it.|
|Flow|[Getting started with dag flow](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/get-started/quickstart.ipynb)|A quickstart tutorial to run a flow and evaluate it.|
|Flow|[Execute flow as a function](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/get-started/flow-as-function.ipynb)|This guide will walk you through the main scenarios of executing flow as a function.|
|Flow|[Run flows in azure ml pipeline](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/run-flow-with-pipeline/pipeline.ipynb)|Create pipeline using components to run a distributed job with tensorflow|
|Flow|[Flow run management in azure](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/run-management/cloud-run-management.ipynb)|Flow run management in Azure AI|
|Flow|[Flow run management](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/run-management/run-management.ipynb)|Flow run management|
|Flow|[Evaluate with langchain's evaluator](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/eval-criteria-with-langchain/langchain-eval.ipynb)|A tutorial to converting LangChain criteria evaluator application to flex flow.|
|Flow|[Getting started with flex flow in azure](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/basic/flex-flow-quickstart-azure.ipynb)|A quickstart tutorial to run a flex flow and evaluate it in Azure.|
|Flow|[Chat with class based flex flow in azure](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/chat-basic/chat-with-class-based-flow-azure.ipynb)|A quickstart tutorial to run a class based flex flow and evaluate it in azure.|
|Flow|[Run dag flow in azure](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/get-started/quickstart-azure.ipynb)|A quickstart tutorial to run a flow in Azure AI and evaluate it.|
|Deployment|[Create service with flow](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/create-service-with-flow/README.md)| This example shows how to create a simple service with flow|
|Deployment|[Deploy a flow using docker](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/docker/README.md)| This example demos how to deploy flow as a docker app|
|Deployment|[Distribute flow as executable app](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/distribute-flow-as-executable-app/README.md)| This example demos how to package flow as a executable app|
|Deployment|[Deploy flow using azure app service](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/azure-app-service/README.md)| This example demos how to deploy a flow using Azure App Service|
|Deployment|[Deploy flow using kubernetes](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-deploy/kubernetes/README.md)| This example demos how to deploy flow as a Kubernetes app|
|Rag|[Tutorial: chat with pdf](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/e2e-development/chat-with-pdf.md)| Retrieval Augmented Generation (or RAG) has become a prevalent pattern to build intelligent application with Large Language Models (or LLMs) since it can infuse external knowledge into the model, which is not trained with those up-to-date or proprietary information|
|Rag|[Tutorial: how prompt flow helps on quality improvement](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/flow-fine-tuning-evaluation/promptflow-quality-improvement.md)| This tutorial is designed to enhance your understanding of improving flow quality through prompt tuning and evaluation|
|Rag|[Chat with pdf - test, evaluation and experimentation](https://github.com/microsoft/promptflow/blob/main/examples/flows/chat/chat-with-pdf/chat-with-pdf.ipynb)|A tutorial of chat-with-pdf flow that allows user ask questions about the content of a PDF file and get answers|
|Rag|[Develop copilot with promptflow](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/develop-copilot-with-promptflow/develop-copilot-with-promptflow.md)| In this tutorial, we will provide a detailed walkthrough on creating a RAG-based copilot using the Azure Machine Learning promptflow toolkit|
|Rag|[How to generate test data based on documents](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/generate-test-data/README.md)| In this doc, you will learn how to generate test data based on your documents for RAG app|
|Rag|[Chat with pdf in azure](https://github.com/microsoft/promptflow/blob/main/examples/flows/chat/chat-with-pdf/chat-with-pdf-azure.ipynb)|A tutorial of chat-with-pdf flow that executes in Azure AI|


Learn more: [Try out more promptflow examples.](https://github.com/microsoft/promptflow/tree/main/examples)