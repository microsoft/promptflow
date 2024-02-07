# How to generate test data based on documents
In this doc, you may learn how to generate test data based on your documents for RAG app.
This approach helps relieve the efforts of manual data creation, which is typically time-consuming and labor-intensive, or the expensive option of purchasing pre-packaged test data.
By leveraging the capabilities of llm, this guide streamlines the test data generation process, making it more efficient and cost-effective.


## Prerequisites

1. Prepare documents. The test data generator supports the following file types:
    - .md - Markdown
    - .docx - Microsoft Word
    - .pdf - Portable Document Format
    - .ipynb - Jupyter Notebook
    - .txt - Text

    **Limitations:**

    - The test data generator may not function effectively for non-Latin characters, such as Chinese, in certain document types. The limitation is caused by dependent text loader capabilities, such as `pypdf`.
    - The test data generator may not generate meaningful questions if the document is not well-organized or contains massive code snippets/links, such as API introduction documents or reference documents.

2. Prepare local environment. Go to [example_gen_test_data](../../examples/gen_test_data) folder and install required packages.

    ```bash
    pip install -r requirements.txt
    ```
  
    For specific document file types, you may need to install extra packages:
      - .docx - `pip install docx2txt`
      - .pdf - `pip install pypdf`
      - .ipynb - `pip install nbconvert`
      > !Note: We use llama index `SimpleDirectoryReader` to load documents. For the latest information on required packages, please check [here](https://docs.llamaindex.ai/en/stable/examples/data_connectors/simple_directory_reader.html).

3. Install VSCode extension `Prompt flow`.

4. [Create connections](https://microsoft.github.io/promptflow/how-to-guides/manage-connections.html#create-a-connection)

5. Prepare config.ini
    - Navigate to [example_gen_test_data](../../examples/gen_test_data) folder.
    - Run command to copy [`config.ini.example`](../../examples/gen_test_data/config.ini.example).
        ```
        cp config.ini.example config.ini
        ```
    - Update the configurations in the `configs.ini`. Fill in the values in `COMMON` and `LOCAL` section following inline comment instruction.


## Create a test data generation flow
  - Open the [sample test data generation flow](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/) in VSCode. This flow is designed to generate a pair of question and suggested answer based on the given text chunk. The flow also includes validation prompts to ensure the quality of the generated test data.
  - Fill in node inputs including `connection`, `model_or_deployment_name`, `response_format`, `score_threshold` or other parameters. Click run button to test the flow in VSCode by referring to [Test flow with VS Code Extension](https://microsoft.github.io/promptflow/how-to-guides/init-and-test-a-flow.html#visual-editor-on-the-vs-code-for-prompt-flow).

    > !Note: Recommend to use `gpt-4` series models than the `gpt-3.5` for better performance.

    > !Note: Recommend to use `gpt-4` model (Azure OpenAI `gpt-4` model with version `0613`) than `gpt-4-turbo` model (Azure OpenAI `gpt-4` model with version `1106`) for better performance. Due to inferior performance of `gpt-4-turbo` model, when you use it, sometimes you might need to set the `response_format` input of nodes `validate_text_chunk`, `validate_question`, and `validate_suggested_answer` to `json`, in order to make sure the llm can generate valid json response.

  - [*Optional*] Customize your test data generation logic refering to [tune-prompts-with-variants](https://microsoft.github.io/promptflow/how-to-guides/tune-prompts-with-variants.html). 

    **Understand the prompts**
    
    The test data generation flow contains 5 prompts, classified into two categories based on their roles: generation prompts and validation prompts. Generation prompts are used to create questions, suggested answers, etc., while validation prompts are used to verify the validity of the text chunk, generated question or answer.
    - Generation prompts
      - [*generate question prompt*](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/generate_question_prompt.jinja2): frame a question based on the given text chunk.
      - [*generate suggested answer prompt*](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/generate_suggested_answer_prompt.jinja2): generate suggested answer for the question based on the given text chunk.
    - Validation prompts
      - [*score text chunk prompt*](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/score_text_chunk_prompt.jinja2): score 0-10 to validate if the given text chunk is worthy of framing a question. If the score is lower than `score_threshold` (default 4), validation fails.
      - [*validate question prompt*](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/validate_question_prompt.jinja2): validate if the generated question is good.
      - [*validate suggested answer*](../../examples/gen_test_data/gen_test_data/generate_test_data_flow/validate_suggested_answer_prompt.jinja2): validate if the generated suggested answer is good.

      If the validation fails, would lead to empty string `question`/`suggested_answer` which are removed from final output test data set.

## Generate test data
- Navigate to [example_gen_test_data](../../examples/gen_test_data) folder.
 
- After configuration, run the following command to generate the test data set:
  ```bash
  python -m gen_test_data.run
  ``` 

- The generated test data will be a data jsonl file. See detailed log print in console "Saved ... valid test data to ..." to find it.

If you expect to generate a large amount of test data beyond your local compute capability, you may try generating test data in cloud, please see this [guide](../cloud/azureai/generate-test-data-cloud.md) for more detailed steps.
