# Installation

The prompt flow SDK & CLI are currently undergoing active development. We will regularly release a stable version to [the stable pypi index](https://pypi.org/project/promptflow/#history). 
This guide will walk you through the installation process for the prompt flow SDK & CLI library.

[SDK Changelog](https://microsoft.github.io/promptflow/reference/changelog/promptflow.html) contains the history of 
stable releases. The feature set of upcoming release will also be available on this page.

Latest stable version:
[![PyPI version](https://badge.fury.io/py/promptflow.svg)](https://badge.fury.io/py/promptflow)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/promptflow)](https://pypi.org/project/promptflow/)

## Create a virtual environment (optional)
When installing prompt flow locally, we recommend using a virtual environment for the installation. This ensures
that the dependencies for prompt flow are isolated from the rest of your system. Please ensure you have a working 
python environment (python>=3.8,<4.0), a new virtual environment is preferred.

::::{tab-set}
:::{tab-item} venv
:sync: venv

To create and activate:
```shell
python3 -m venv pf
source pf/bin/activate
```
To deactivate later, run:
```shell
deactivate
```

:::

:::{tab-item} Conda
:sync: Conda
[Install Conda](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html) if you have not already.
To create and activate:
```shell
conda create -n pf python=3.11
conda activate pf
```
To deactivate later, run:
```shell
conda deactivate
```

:::

::::

## Install prompt flow
You can run below command to install the latest version of the promptflow to work with flows locally.

```shell
# Install the latest stable version
pip install promptflow --upgrade
```
After developing your flow locally, you can seamlessly transition to Azure AI and interact with your flow in the cloud. 
Use the following command to install the latest version of prompt flow to work with flows in Azure.

```shell
# Install the latest stable version
pip install promptflow[azure] --upgrade
```

## Promptflow sub packages
Prompt flow consists of several sub-packages, each is designed to provide specific functionalities.

| Name                                                                | Description                                                                                                                                                                                                                |
|---------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [promptflow-tracing](https://pypi.org/project/promptflow-tracing/)  | The `promptflow-tracing` package offers tracing capabilities to capture and illustrate the internal execution processes of both DAG flow and Flex flow.                                                                    |
| [promptflow-core](https://pypi.org/project/promptflow-core/)        | The `promptflow-core` package provides the essential features needed to execute a flow in prompt flow.                                                                                                                     |
| [promptflow-devkit](https://pypi.org/project/promptflow-devkit/)    | The `promptflow-devkit` package offers features like: create and iteratively develop flow, evaluate flow quality and performance, and a streamlined development cycle for production.                                      |
| [promptflow-azure](https://pypi.org/project/promptflow-azure/)      | The `promptflow-azure` package helps user to leverage the cloud version of [prompt flow in Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/overview-what-is-prompt-flow?view=azureml-api-2) |

## Verify installation
To verify the installation, run the following command to check the version of prompt flow installed.

```shell
pf --version
```

Running the above command will yield the following example output:
```
{
  "promptflow": "1.10.1",
  "promptflow-core": "1.10.1",
  "promptflow-devkit": "1.10.1",
  "promptflow-tracing": "1.10.1"
}
```

```{toctree}
:maxdepth: 1
:hidden:

standalone
```