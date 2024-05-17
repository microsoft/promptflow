# How to generate test data in cloud based on documents
This guide will help you learn how to generate test data on Azure AI, so that you can integrate the created flow and process a large amount of data.


## Prerequisites

1. Go through [local test data generation guide](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/generate-test-data/README.md) and prepare your [test data generation flow](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/generate-test-data/example_flow).
2. Go to the [example_gen_test_data](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/generate-test-data) folder and run command `pip install -r requirements_cloud.txt` to prepare local environment.
3. Prepare cloud environment.
    - Navigate to file [conda.yml](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/generate-test-data/conda.yml).
    - For specific document file types, you may need to install extra packages:
      - .docx - `pip install docx2txt`
      - .pdf - `pip install pypdf`
      - .ipynb - `pip install nbconvert`
      > !Note: We use llama index `SimpleDirectoryReader` to load documents. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).

4. Prepare Azure AI resources in cloud.
    - An Azure AI ML workspace - [Create workspace resources you need to get started with Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/quickstart-create-resources?view=azureml-api-2).
    - A compute target - [Learn more about compute cluster](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target?view=azureml-api-2).
5. [Create cloud AzureOpenAI or OpenAI connection](https://microsoft.github.io/promptflow/cloud/azureai/run-promptflow-in-azure-ai.html#create-necessary-connections)

6. Prepare test data generation setting.
    - Navigate to [example_gen_test_data](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/generate-test-data) folder.
    - Prepare `config.yml` by copying [`config.yml.example`](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/generate-test-data/config.yml.example).
    - Fill in configurations in the `config.yml` by following inline comment instructions.


## Generate test data at cloud
For handling larger test data, you can leverage the PRS component to run flow in cloud.
- Navigate to [example_gen_test_data](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/generate-test-data) folder.
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m generate-test-data.run --cloud
  ```

- The generated test data will be a data asset which can be found in the output of the last node. You can register this data asset for future use.
