# Smart Vector DB Lookup

The Smart Vector DB Look up is a tool focused on providing the best query results from a AzureML MlIndex vector store. By leveraging the capabilities of OpenAi or AzureOpenAI, the Smart Vector DB lookup tool pin-points the most contextually relevant information from a domain knowledge base for optimum response quality from our Large Language Model (LLM) tool.

## Requirements

- For AzureML users, the tool is installed in default image, you can use the tool without extra installation.
- For local users, if your index is stored in local path,
  
  `pip install promptflow-vectordb[azure]`

## Prerequisites

1. Create an OpenAI resource:

   - **OpenAI**: Sign up account [OpenAI website](https://openai.com/). Login and [Find personal API key](https://platform.openai.com/account/api-keys)

   - **Azure OpenAI (AOAI)**: Create Azure OpenAI resources with [insturction](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal)

2. Create a MlIndex Vector store via either of the following two options:

   1. [Create a vector index in an Azure Machine Learning prompt flow](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-create-vector-index?view=azureml-api-2)
   2. [Create a FAISS based Vector Index using AzureML Pipelines](https://github.com/Azure/azureml-examples/blob/main/sdk/python/generative-ai/rag/notebooks/faiss/faiss_mlindex_with_langchain.ipynb)

## Inputs

The tool accepts the following inputs:

| Name | Type | Description | Required |
| ---- | ---- | ----------- | -------- |
| vector_index_path | string | URL or path for the vector store.<br><br>local path (for local users):<br>`<local_path_to_the_index_folder>`<br><br> Azure blob URL format (with [azure] extra installed):<br>https://`<account_name>`.blob.core.windows.net/`<container_name>`/`<path_and_folder_name>`.<br><br>AML datastore URL format (with [azure] extra installed):<br>azureml://subscriptions/`<your_subscription>`/resourcegroups/`<your_resource_group>`/workspaces/`<your_workspace>`/data/`<data_path>`<br><br>public http/https URL (for public demonstration):<br>http(s)://`<path_and_folder_name>` | Yes |
| embedding_aoai_connection | AzureOpenAIConnection, OpenAI | Connection to access an AOAI or Open AI Embedding model | Yes |
| generative_aoai_connection | AzureOpenAIConnection, OpenAI | Connection to access an AOAI or Open AI Completion model | Yes |
| query | string | This is the users input or question | Yes |
| scenario | string | This is meta data that informs the tool as to it's corpus focus. For example "Azure Kubernetes Service" | Yes |
| embedding_deployment_name | string | The embedding model name. Default: text-embedding-ada-002 | False |
| generative_deployment_name | string | The completion model name. Default: gpt-35-turbo | False |
| top_k | int | The number of documents to return for each generated filter. Does not correspond to the number of documents returned from this tool. Default: 5 | False |
| max_tokens_returned | int | This limits the number of documents which are returned by the tool, by the estimated tokens used by the test content. Default: 3000 | False |

## Outputs

The following is an example for JSON format response returned by the tool, which includes the top-k scored entities. The entity follows a generic schema of vector search result. The following fields are populated:

| Field Name | Type | Description |
| ---- | ---- | ----------- |
| Title | string | The the title of the document chunk |
| Url | string | This is a link to the source of the document chunk |
| Text | string | Text of the entity |
| Score | float | The measurement of similarity or relevance, depends on the underlying index. |

<details>
  <summary>Output</summary>
  
```json
[
  {
    "Score": 0,
    "Text": "sample text #0",
    "Title": "title0",
    "Url": "http://sample_link_0",
  },
  {
    "Score": 0.05000000447034836,
    "Text": "sample text #1",
    "Title": "title1",
    "Url": "http://sample_link_1"
  },
  {
    "Score": 0.20000001788139343,
    "Text": "sample text #2",
    "Title": "title2",
    "Url": "http://sample_link_2"
  }
]

```
</details>