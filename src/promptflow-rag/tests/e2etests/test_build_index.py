import json
import os
import pathlib
import pytest
from datetime import datetime as dt
from promptflow.rag.resources import LocalSource, AzureAISearchConfig

from promptflow.rag import build_index


@pytest.fixture
def input_source():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return LocalSource(input_data=os.path.join(data_path, "product-info"))

@pytest.mark.usefixtures("embeddings_model_config", "index_connection_config", "input_source")
@pytest.mark.e2etest
def test_local_input_with_aoai_model(embeddings_model_config, index_connection_config, input_source):
    local_index_name = "local-test-" + dt.now().strftime("%Y-%m-%d-%H-%M-%S")
    index_path=build_index(
        name=local_index_name,
        vector_store="azure_ai_search",
        embeddings_model_config=embeddings_model_config,
        input_source=input_source,  # the location of your file/folders
        index_config=AzureAISearchConfig(
            ai_search_index_name=local_index_name + "-store", # the name of the index store inside the azure ai search service
            ai_search_connection_config=index_connection_config
        ),
        tokens_per_chunk = 800, # Optional field - Maximum number of tokens per chunk
        token_overlap_across_chunks = 0, # Optional field - Number of tokens to overlap between chunks
    )
    assert index_path is not None
    with open(
        file=index_path,
        mode="r",
    ) as f:
        mlindex = json.load(f)
    print(mlindex)
