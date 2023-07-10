# Prompt-flow examples

Welcome to the prompt flow examples repository!

## Prerequisites

- Bootstrap your python env. 
  - e.g: create a new [conda](https://conda.io/projects/conda/en/latest/user-guide/getting-started.html) environment. `conda create -n pf-examples python=3.9`.
  - install required packages in python environment : `pip install -r requirements.txt`


## Examples

**Flows** ([flows](flows))

standard flows:
path|status|description
-|-|-
[basic](flows/standard/basic/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a basic flow with prompt and python tool.
[basic-with-connection](flows/standard/basic-with-connection/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a basic flow using custom connection with prompt and python tool
[basic-with-builtin-llm](flows/standard/basic-with-builtin-llm/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a basic flow using builtin llm tool
[intent-copilot](flows/standard/intent-copilot/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a flow created from existing langchain python code
[flow-with-symlinks](flows/standard/flow-with-symlinks/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a flow created with external code reference
[web-classification](flows/standard/web-classification/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a flow demonstrating multi-class classification with LLM. Given an url, it will classify the url into one web category with just a few shots, simple summarization and classification prompts.

evaluation flows:
path|status|description
-|-|-
[basic-eval](flows/standard/basic-eval/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a basic evaluation flow.
[classification-accuracy-eval](flows/standard/classification-accuracy-eval/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a flow illustrating how to evaluate the performance of a classification system.

chat flows:
path|status|description
-|-|-
[basic-chat](flows/standard/basic-chat/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a basic chat flow.
[chat-with-wikipedia](flows/standard/chat-with-wikipedia/flow.dag.yaml)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)| a flow demonstrating Q&A with GPT3.5 using information from Wikipedia to make the answer more grounded. 

**Tutorials** ([tutorials](tutorials))
path|status|
-|-
[quickstart.ipynb](tutorials/get-started/quickstart.ipynb)|[![batch-score-rest](https://github.com/Azure/azureml-examples/workflows/cli-scripts-batch-score-rest/badge.svg?branch=main)](https://github.com/Azure/azureml-examples/actions/workflows/cli-scripts-batch-score-rest.yml)

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
