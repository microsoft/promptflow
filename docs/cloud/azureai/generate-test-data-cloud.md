# How to generate test data in cloud based on documents
This guide will help you learn how to generate test data on Azure AI, so that you can integrate the created flow and process a large amount of data.


## Prerequisites

1. Go through local test data generation [guide](../../how-to-guides/generate-test-data.md) and prepare your test data generation flow.
2. Go to the [gen_test_data](../../../examples/gen_test_data) folder and run command `pip install -r requirements_cloud.txt` to prepare local environment.
3. Prepare cloud environment.
    - Navigate to file [conda.yml](../../../examples/gen_test_data/conda.yml).
    - For specific document file types, you may need to add extra packages in `conda.yml`:
        > !Note: We use llama index `SimpleDirectoryReador` in this process. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).
        - .docx - `docx2txt`
        - .pdf - `pypdf`
        - .ipynb - `nbconvert`

4. Create cloud connection: [Create a connection](https://microsoft.github.io/promptflow/cloud/azureai/quick-start.html#create-necessary-connections)
5. Prepare Azure AI resources in cloud.
    - An Azure AI ML workspace - [Create workspace resources you need to get started with Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/quickstart-create-resources?view=azureml-api-2).
    - A compute target - [Learn more about compute cluster](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target?view=azureml-api-2).
6. Set configs
    If you have already generated `configs.ini` file, just fill in the values in `COMMON` and `CLOUD` sections. Otherwise, navigate to [gen_test_data](../../../examples/gen_test_data) folder, run `cp config.ini.example config.ini` to generate the `configs.ini` file


## Generate test data at cloud
For handling larger test data, you can leverage the PRS component to run flow in cloud.
- Navigate to [gen_test_data](../../../examples/gen_test_data) folder.
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m gen_test_data.run --cloud
  ``` 
  
- The generated test data will be a data asset which can be found in the output of the last node. You can register this data asset for future use.
