# How to construct test data based on documents
This guide will instruct you on how to generate test data for RAG systems utilizing existing documents.
Previously evaluating the performance of RAG systems required the creation of test data. This could be done manually, a process that required significant time and effort, or by purchasing pre-made test data, which could be costly.

This test data generation process streamlines this by leveraging the capabilities of llm to automatically generate the test data. This not only reduces the effort required but also eliminates the need for additional expenditures.

By following this guide, you will learn how to:
1. Customize the test data generation process by tuning flow prompts.
2. Generate high-quality test data quickly and easily by running a test data generation script.

**Supported file types**
- .md - Markdown
- .docx - Microsoft Word
- .pdf - Portable Document Format
- .ipynb - Jupyter Notebook

**Limitations**

- While the test data generator works well with standard documents, it may face challenges with API introduction documents or reference documents.
- Additionally, it may not function effectively for non-Latin characters, such as Chinese. These limitations may be due to the text loader capabilities such as pypdf.

## Quick start
- Install required packages
Enter `test_data_gen_local` folder, run below command to install required packages.
  ```bash
  pip install -r requirements.txt
  ```

  For specific document file types, you will need to install extra packages:
  > !Note: This package requirement may be outdated. In this process, we utilize llama index `SimpleDirectoryReador`. For the most recent information, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).
  - .docx - `pip install docx2txt`
  - .pdf - `pip install pypdf`
  - .ipynb - `pip install nbconvert`

- Run and tune test data construction flow
  - Navigate to the [construct_test_data_flow folder](../../examples/test_data_gen/construct_test_data_flow/). Open the `flow.dag.yaml` to understand the structure of the data flow. Fill in necessary values like connections and model/deployment name.
  - Ensure the `flow.tools.json` is generated under `.promptflow` folder within the flow folder.
  - Check the guide [init-and-test-a-flow](https://microsoft.github.io/promptflow/how-to-guides/init-and-test-a-flow.html) to test the flow.
  - [*Optional*] Customize your test data generation logic. Refer to [tune-prompts-with-variants](https://microsoft.github.io/promptflow/how-to-guides/tune-prompts-with-variants.html) for more guidance. Once you updated the flow, ensure the flow can complete successfully before preceding to next steps to generate bulk data.
  
  **Understand the prompts**
  
  The test data construction flow contains five different prompts, classified into two categories based on their roles: generation prompts and validation prompts. Generation prompts are used to create questions, suggested answers, etc., while validation prompts are used to verify the validity of the text trunk, generated question or answer.
  - Generation prompts
    - *generate question prompt*: frame a question based on the given text trunk.
    - *generate suggested answer prompt*: generate suggested answer for the question based on the given text trunk.
  - Validation prompts
    - *score text trunk prompt*: validate if the given text trunk is worthy of framing a question. If the score is lower than score_threshold, validation fails.
    - *validate seed/test question prompt*: validate if the generated question can be clearly understood.
    - *validate suggested answer*: validate if the generated suggested answer is clear and certain.

    If the validation fails, the corresponding output would be an empty string so that the invalid data would not be incorporated into the final test data set.
  
  **Set the appropriate model and corresponding response format**:
  
  The `gpt-4` model is recommended. The default prompt may yield better results with this model compared to the gpt-3 series.
  - For the `gpt-4` model with version `0613`, use the response format `text`.
  - For the `gpt-4` model with version `1106`, use the response format `json`.

- Run data generation script
    - Enter [test_data_gen_local folder](../../examples/test_data_gen/test_data_gen_local).
    - Update the configurations in the `configs.ini` file. Here is a brief of introduction of each parameter:
      > // TODO: or move this part as comment in config ini?
      - *should_skip_doc_split*: Document split step can be reused. If you have already splitted the documents, and in next time you just want to generate the test data based on these document chunks, you can set the value as `True` to skip the document split step.
      - *documents_folder*: the source path of text to be splitted into text trunks for question and answer generation.
      - *document_chunk_size*: chunk size is used to determine the size of each text chunk
        > !Note: In this guidance, we leverage llama_index to do text chunking. There are two steps of document splitting:
        >
        >     a. Each document would be splitted roughly based on different document file types. Markdown file would be splitted by Heading, pdf file would be splitted by pages.
        >     b. For each splitted document chunk, it would get further splitted by chunk size. Chunk size may not seem to work if the text token size is smaller than chunk size.
      - *document_nodes_output_path*: //TODO: make it a default folder without need to configure.
      - *flow_folder*: //TODO: can we use relative path so that there is no need to configure the flow folder path either.
      - *connection_name*: //TODO: do we need to provide the option to override the connection in script.
      - *test_data_output_path*: output path of generated test data set.
    - After configuration, run the following command to generate the test data set:
      ```bash
      python run_test_data_gen.py
      ```
    - The generated test data will be a data jsonl file located in the path you configured in `config.ini`.


## Cloud
For handling larger test data, you can leverage the PRS component to run flow in pipeline.
- Prerequisites
  Enter `test_data_gen_pipeline` folder, run below command to install required packages.
  ```bash
  pip install -r requirements.txt
  ```

- Enter [test_data_gen_pipeline folder](../../examples/test_data_gen/test_data_gen_pipeline)
    - Update configs in `configs.ini`
    - After configuration, run below command to gen test data set.
      ```bash
      python run_test_data_gen_pipeline.py
      ```
    - The generated test data will be a data asset which can be found in the output of the last node. You can register this data asset for future use.
