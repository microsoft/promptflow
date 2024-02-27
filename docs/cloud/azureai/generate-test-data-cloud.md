# How to generate test data in cloud based on documents
This guide will help you learn how to generate test data on Azure AI, so that you can integrate the created flow and process a large amount of data.


## Prerequisites

1. Go through [local test data generation guide](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/docs/how-to-guides/generate-test-data.md) and prepare your [test data generation flow](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data/gen_test_data/generate_test_data_flow/).
2. Go to the [example_gen_test_data](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data) folder and run command `pip install -r requirements_cloud.txt` to prepare local environment.
3. Prepare cloud environment.
    - Navigate to file [conda.yml](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data/conda.yml).
    - For specific document file types, you may need to install extra packages:
      - .docx - `pip install docx2txt`
      - .pdf - `pip install pypdf`
      - .ipynb - `pip install nbconvert`
      > !Note: We use llama index `SimpleDirectoryReader` to load documents. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).

4. Prepare Azure AI resources in cloud.
    - An Azure AI ML workspace - [Create workspace resources you need to get started with Azure AI](https://learn.microsoft.com/en-us/azure/machine-learning/quickstart-create-resources?view=azureml-api-2).
    - A compute target - [Learn more about compute cluster](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target?view=azureml-api-2).
5. [Create cloud connection](https://microsoft.github.io/promptflow/cloud/azureai/quick-start/index.html#create-necessary-connections)

6. Prepare config.ini
    - Navigate to [example_gen_test_data](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data) folder.
    - Run command to copy [`config.yml.example`](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data/config.yml.example).
        ```
        cp config.yml.example config.yml
        ```
    - Update the configurations in the `configs.yml`. Fill in the values in `Common` and `Cloud` section following inline comment instruction.


## Generate test data at cloud
For handling larger test data, you can leverage the PRS component to run flow in cloud.
- Navigate to [example_gen_test_data](https://github.com/microsoft/promptflow/blob/6f08f091041c32c6e1cbe3d386c734ba8000867e/examples/gen_test_data) folder.
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m gen_test_data.run --cloud
  ``` 
  
- The generated test data will be a data asset which can be found in the output of the last node. You can register this data asset for future use.
