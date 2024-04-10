# Prompflow-rag

The promptflow-rag package is part of the Promptflow sdk and contains functionality for building indexes locally

## Getting started

### Prerequisites

- Python 3.7 or later is required to use this package.
- You must have an [Azure subscription][azure_subscription].
- An [Azure Machine Learning Workspace][workspace].
- An [Azure AI Studio project][ai_project].

### Install the package

Install the Azure AI generative package for Python with pip:

```
pip install prompflow-rag
```

## Usage

### Create index locally

Users can create an index on their local machine from local source files using the `build_index` method. Given below is a sample.

```python
from promptflow.rag.resources import LocalSource, AzureAISearchConfig, EmbeddingsModelConfig
from promptflow.rag import build_index

# build the index
ai_search_index_path=build_index(
    name=index_name,  # name of your index
    vector_store="azure_ai_search",  # the type of vector store - in this case it is Azure AI Search.
    embeddings_model_config=EmbeddingsModelConfig(
        embeddings_model=f"azure_open_ai://deployment/{embedding_model_deployment}/model/{embedding_model_name}"
    )
    input_source=LocalSource(input_data="data/product-info/"),  # the location of your file/folders
    index_config=AzureAISearchConfig(
        ai_search_index_name=ai_search_index_name # the name of the index store inside the azure ai search service
    )
)
```

The build index will return the path where the index was created.

## Examples

# TODO: add link to sample notebooks

<!-- LINKS -->

[ai_project]: https://aka.ms/azureaistudio
[azure_subscription]: https://azure.microsoft.com/free/
[workspace]: https://docs.microsoft.com/azure/machine-learning/concept-workspace
