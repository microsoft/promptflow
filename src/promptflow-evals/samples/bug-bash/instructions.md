# Promptflow Evals Bug Bash Instructions

## Welcome to the Promptflow Evals Bug Bash!

### Prerequisites
- Azure Open AI Endpoint
- Open AI Model Deployment that supports `chat completion`
- Azure AI Project
  - Needed for content safety metrics. Project should be in one of the following reason if you would like to try out content safety evaluators
    - `East US 2`
    - `Sweden Central`
    - `France Central`
    - `UK South`
  - For local to remote tracking

Note: You need the new [gpt-35-turbo (0125) version](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#gpt-35-models) to use the json_object response_format feature. This might be needed for some prompty based evaluators.

### Clone the repo
```bash
git clone https://github.com/microsoft/promptflow.git
git pull
git checkout -b user/singankit/pf-evals-bug-bash
```

### Installation Instructions:

1. Create a **virtual environment of you choice**. To create one using conda, run the following command:
    ```bash
    conda create -n promptflow-evals-bug-bash python=3.10
    ```
2. Install the required packages by running the following command:
    ```bash
   # Clearing any old installation
   # This is important since older version of promptflow has one package.
   # Now it is split into number of them.
    pip uninstall promptflow promptflow-azure promptflow-core promptflow-devkit promptflow-tools promptflow-evals

   # Install packages in this order
   pip install promptflow==1.10.0.dev125439426 --extra-index-url https://azuremlsdktestpypi.azureedge.net/promptflow
   pip install promptflow-evals==0.2.0.dev125439426 --extra-index-url https://azuremlsdktestpypi.azureedge.net/promptflow
   pip install azure_ai_ml==1.16.0a20240501004 --extra-index-url https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/simple/

   # Dependencies needed for some of the notebooks
   pip install bs4
   pip install ipykernel
    ```
4. To track your local evaluations in cloud run following command to set tracking config after replacing the placeholder values
   ```bash
   pf config set trace.destination=azureml://subscriptions/<subscription_id>/resourceGroups/<resource_group_name>/providers/Microsoft.MachineLearningServices/workspaces/<project_name>
   ```
   To remote tracking config navigate to `C:\Users\<user>\.promptflow` and locate `py.yaml` file and delete the `trace:` section
4. To run the examples from the notebook, please install the kernel in your environment:
   ```bash
   python -m ipykernel install --user --name promptflow-evals-bug-bash --display-name "promptflow-evals-bug-bash"
   ```
6. Select the newly installed kernel in the Jupyter notebook.

### Report Bugs

Please use the following template to report bugs : [**Bug Template**](https://aka.ms/aicodefirst/createbug)

### Sample Notebooks

1. Evaluate existing dataset - [Notebook Link](./evaluate-using-data/evaluate-using-data.ipynb)
2. Evaluate Target. Target can be a chat app locally or deployed to an endpoint. - [Notebook Link](./evaluate-target/evaluate-target.ipynb)
3. Create new evaluators and registering them in cloud - [Notebook Link](./LoadSaveEvals/Load_saved_evaluator.ipynb)
