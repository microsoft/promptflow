# How to generate test data based on documents
This guide will instruct you on how to generate test data for RAG systems using pre-existing documents.
This approach eliminates the need for manual data creation, which is typically time-consuming and labor-intensive, or the expensive option of purchasing pre-packaged test data.
By leveraging the capabilities of llm, this guide streamlines the test data generation process, making it more efficient and cost-effective.


## Prerequisites

1. Prepare documents. The test data generator supports the following file types:
    - .md - Markdown
    - .docx - Microsoft Word
    - .pdf - Portable Document Format
    - .ipynb - Jupyter Notebook

    **Limitations:**

    - While the test data generator works well with standard documents, it may face challenges with API introduction documents or reference documents.
    - The test data generator may not function effectively for non-Latin characters, such as Chinese. These limitations may be due to the text loader capabilities, such as `pypdf`.

2. Go to the [gen_test_data](../../examples/gen_test_data) folder and install required packages. 
    - Run in local: `pip install -r requirements.txt`
    - Run in cloud: `pip install -r requirements_cloud.txt`
  
    For specific document file types, you will need to install extra packages:
      > !Note: We use llama index `SimpleDirectoryReador` in this process. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).
      - .docx - `pip install docx2txt`
      - .pdf - `pip install pypdf`
      - .ipynb - `pip install nbconvert`

3. Install VSCode extension and create connections refer to [Create a connection](https://microsoft.github.io/promptflow/how-to-guides/manage-connections.html#create-a-connection)


## Create a test data generation flow
  - Open the [generate_test_data_flow](../../examples/gen_test_data/generate_test_data_flow/) folder in VSCode. 


  - [*Optional*] Customize your test data generation logic refering to [tune-prompts-with-variants](https://microsoft.github.io/promptflow/how-to-guides/tune-prompts-with-variants.html). 

    **Understand the prompts**
    
    The test data generation flow contains five different prompts, classified into two categories based on their roles: generation prompts and validation prompts. Generation prompts are used to create questions, suggested answers, etc., while validation prompts are used to verify the validity of the text trunk, generated question or answer.
    - Generation prompts
      - *generate question prompt*: frame a question based on the given text trunk.
      - *generate suggested answer prompt*: generate suggested answer for the question based on the given text trunk.
    - Validation prompts
      - *score text trunk prompt*: validate if the given text trunk is worthy of framing a question. If the score is lower than score_threshold, validation fails.
      - *validate seed/test question prompt*: validate if the generated question can be clearly understood.
      - *validate suggested answer*: validate if the generated suggested answer is clear and certain.

      If the validation fails, the corresponding output would be an empty string so that the invalid data would not be incorporated into the final test data set.
    
  
  
  - Fill in the necessary flow/node inputs, and run the flow in VSCode refering to [Test flow with VS Code Extension](https://microsoft.github.io/promptflow/how-to-guides/init-and-test-a-flow.html#visual-editor-on-the-vs-code-for-prompt-flow).

    **Set the appropriate model and corresponding response format.** The `gpt-4` model is recommended. The default prompt may yield better results with this model compared to the gpt-3 series.
      - For the `gpt-4` model with version `0613`, use the response format `text`.
      - For the `gpt-4` model with version `1106`, use the response format `json`.

 
## Generate test data at local
- Navigate to [gen_test_data](../../examples/gen_test_data_gen) folder.

- Run command to copy `config.ini.example` and update the `COMMON` and `LOCAL` configurations in the `configs.ini` file
    ```
    cp config.ini.example config.ini
    ```
  
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m gen_test_data.run
  ```
- The generated test data will be a data jsonl file located in the path you configured in `config.ini`.


## Generate test data at cloud
For handling larger test data, you can leverage the PRS component to run flow in cloud. Please refer to this [guide](../cloud/azureai/generate-test-data-cloud.md) for more information.
