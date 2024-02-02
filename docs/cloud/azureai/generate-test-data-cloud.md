# How to generate test data based on documents
This guide will help you learn how to generate test data in a pipeline job on AzureML, so that you can integrate the created flow with existing pipelines and process a large amount of data.


## Prerequisites

1. Go through local gen test data [doc](../../how-to-guides/generate-test-data.md) and prepare your test data generation flow.
2. Go to the [gen_test_data](../../../examples/gen_test_data) folder and run command `pip install -r requirements_cloud.txt` to prepare local environment.
3. Prepare environment required to run the component.
    - Navigate to file [conda.yml](../../../examples/gen_test_data/conda.yml).
    - For specific document file types, you will need to add extra packages in `conda.yml`:
        > !Note: We use llama index `SimpleDirectoryReador` in this process. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).
        - .docx - `pip install docx2txt`
        - .pdf - `pip install pypdf`
        - .ipynb - `pip install nbconvert`

4. Create cloud connection: [Create a connection](https://microsoft.github.io/promptflow/how-to-guides/manage-connections.html#create-a-connection)
5. Prepare cloud env
    - An Azure AI ML workspace - [Create workspace resources you need to get started with Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/quickstart-create-resources?view=azureml-api-2).
    - A compute target - [Learn more about compute cluster](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target?view=azureml-api-2).
6. Configure configs
    - Navigate to [gen_test_data](../../../examples/gen_test_data_gen) folder.
    - Run command to copy `cloud.config.ini.example` and update the configurations in the `cloud.configs.ini` file
        ```
        cp cloud.config.ini.example cloud.config.ini
        ```
    - Fill in the values.


## Generate test data at cloud
For handling larger test data, you can leverage the PRS component to run flow in pipeline.
- Navigate to [gen_test_data](../../../examples/gen_test_data_gen) folder.
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m gen_test_data.run --cloud
  ``` 
  
- The generated test data will be a data asset which can be found in the output of the last node. You can register this data asset for future use.
