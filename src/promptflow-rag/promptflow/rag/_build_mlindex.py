# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Dict, Optional, Union

import yaml  # type: ignore[import]
from packaging import version


from promptflow.rag.constants._common import AZURE_AI_SEARCH_API_VERSION
from promptflow.rag.config import EmbeddingsModelConfig, AzureAISearchConfig, AzureAISearchSource, LocalSource
from promptflow.rag._utils._open_ai_utils import build_open_ai_protocol


def build_index(
    *,
    name: str,
    vector_store: str = "azure_ai_search",
    input_source: Union[AzureAISearchSource, LocalSource],
    index_config: Optional[AzureAISearchConfig] = None,  # todo better name?
    embeddings_model_config: EmbeddingsModelConfig,
    data_source_url: Optional[str] = None,
    tokens_per_chunk: int = 1024,
    token_overlap_across_chunks: int = 0,
    input_glob: str = "**/*",
    max_sample_files: Optional[int] = None,
    chunk_prepend_summary: Optional[bool] = None,
    document_path_replacement_regex: Optional[Dict[str, str]] = None,
    embeddings_cache_path: Optional[str] = None,
) -> str:
    """
    Generates embeddings locally and stores Index reference in memory

    :keyword name: The name of the output index.
    :paramtype name: str
    :keyword vector_store: The vector store to be indexed.
    :paramtype vector_store: str
    :keyword input_source: The configuration for input data source.
    :paramtype input_source: Union[AzureAISearchSource, LocalSource]
    :keyword index_config: The configuration for Azure Cognitive Search output.
    :paramtype index_config: AzureAISearchConfig
    :keyword embeddings_model_config: The configuration for embedding model.
    :paramtype embeddings_model_config: EmbeddingsModelConfig
    :keyword data_source_url: The URL of the data source.
    :paramtype data_source_url: Optional[str]
    :keyword tokens_per_chunk: The size of each chunk.
    :paramtype tokens_per_chunk: int
    :keyword token_overlap_across_chunks: The overlap between chunks.
    :paramtype token_overlap_across_chunks: int
    :keyword input_glob: The input glob pattern.
    :paramtype input_glob: str
    :keyword max_sample_files: The maximum number of sample files.
    :paramtype max_sample_files: Optional[int]
    :keyword chunk_prepend_summary: Whether to prepend summary to each chunk.
    :paramtype chunk_prepend_summary: Optional[bool]
    :keyword document_path_replacement_regex: The regex for document path replacement.
    :paramtype document_path_replacement_regex: Optional[Dict[str, str]]
    :keyword embeddings_cache_path: The path to embeddings cache.
    :paramtype embeddings_cache_path: Optional[str]
    :return: local path to the index created.
    :rtype: str
    """
    try:
        from azureml.rag.documents import DocumentChunksIterator, split_documents
        from azureml.rag.embeddings import EmbeddingsContainer
        from azureml.rag.tasks.update_acs import create_index_from_raw_embeddings
        from azureml.rag.utils.connections import get_connection_by_id_v2
    except ImportError as e:
        print(
            "In order to use build_index to build an Index locally, you must have azureml-rag installed."
        )
        raise e

    is_serverless_connection = False
    if not embeddings_model_config.model_name:
        raise ValueError("Please specify embeddings_model_config.model_name")

    if "cohere" in embeddings_model_config.model_name:
        # If model uri is None, it is *considered* as a serverless endpoint for now.
        # TODO: depends on azureml.rag.Embeddings.from_uri to finalize a scheme for different embeddings
        if not embeddings_model_config.connection_config and not embeddings_model_config.connection_id:
            raise ValueError(
                "Please specify connection_config or connection_id to use serverless connection"
            )
        embeddings_model_uri = None
        is_serverless_connection = True
        print("Using serverless connection.")
    else:
        embeddings_model_uri = build_open_ai_protocol(
            embeddings_model_config.deployment_name,
            embeddings_model_config.model_name
        )
    connection_id = embeddings_model_config.get_connection_id()

    if isinstance(input_source, AzureAISearchSource):
        return _create_mlindex_from_existing_ai_search(
            # TODO: Fix Bug 2818331
            name=name,
            embedding_model_uri=embeddings_model_uri,
            is_serverless_connection=is_serverless_connection,
            connection_id=connection_id,
            ai_search_config=input_source,
        )

    if not index_config:
        raise ValueError("Please provide index_config details")
    embeddings_cache_path = str(Path(embeddings_cache_path) if embeddings_cache_path else Path.cwd())
    save_path = str(Path(embeddings_cache_path) / f"{name}-mlindex")
    splitter_args = {"chunk_size": tokens_per_chunk, "chunk_overlap": token_overlap_across_chunks, "use_rcts": True}
    if max_sample_files is not None:
        splitter_args["max_sample_files"] = max_sample_files
    if chunk_prepend_summary is not None:
        splitter_args["chunk_preprend_summary"] = chunk_prepend_summary

    print(f"Crack and chunk files from local path: {input_source.input_data_path}")
    chunked_docs = DocumentChunksIterator(
        files_source=input_source.input_data_path,
        glob=input_glob,
        base_url=data_source_url,
        document_path_replacement_regex=document_path_replacement_regex,
        chunked_document_processors=[
            lambda docs: split_documents(
                docs,
                splitter_args=splitter_args,
            )
        ],
    )

    connection_args = {}
    if embeddings_model_uri and "open_ai" in embeddings_model_uri:
        if connection_id:
            aoai_connection = get_connection_by_id_v2(connection_id)
            if isinstance(aoai_connection, dict):
                if "properties" in aoai_connection and "target" in aoai_connection["properties"]:
                    endpoint = aoai_connection["properties"]["target"]
            elif aoai_connection.target:
                endpoint = aoai_connection.target
            else:
                raise ValueError("Cannot get target from model connection")
            connection_args = {
                "connection_type": "workspace_connection",
                "connection": {"id": connection_id},
                "endpoint": endpoint,
            }
            print(f"Start embedding using connection with id = {connection_id}")
        else:
            import openai
            import os

            api_key = "OPENAI_API_KEY"
            api_base = "OPENAI_API_BASE"
            if version.parse(openai.version.VERSION) >= version.parse("1.0.0"):
                api_key = "AZURE_OPENAI_KEY"
                api_base = "AZURE_OPENAI_ENDPOINT"
            connection_args = {
                "connection_type": "environment",
                "connection": {"key": api_key},
                "endpoint": os.getenv(api_base),
            }
            print("Start embedding using api_key and api_base from environment variables.")
        embedder = EmbeddingsContainer.from_uri(
            embeddings_model_uri,
            **connection_args,
        )
    elif is_serverless_connection:
        print(f"Start embedding using serverless connection with id = {connection_id}.")
        connection_args = {
            "connection_type": "workspace_connection",
            "connection": {"id": connection_id},
        }
        embedder = EmbeddingsContainer.from_uri(None, credential=None, **connection_args)
    else:
        raise ValueError("embeddings model is not supported")

    embeddings = embedder.embed(chunked_docs)

    if vector_store.lower() == "faiss":
        embeddings.write_as_faiss_mlindex(save_path)
    if vector_store.lower() == "azure_ai_search":
        ai_search_args = {
            "index_name": index_config.ai_search_index_name,
        }
        ai_search_connection_id = index_config.get_connection_id()
        if not ai_search_connection_id:
            import os

            ai_search_args = {
                **ai_search_args,
                **{
                    "endpoint": os.getenv("AZURE_AI_SEARCH_ENDPOINT")
                    if "AZURE_AI_SEARCH_ENDPOINT" in os.environ
                    else os.getenv("AZURE_COGNITIVE_SEARCH_TARGET"),
                    "api_version": AZURE_AI_SEARCH_API_VERSION,
                },
            }
            connection_args = {"connection_type": "environment", "connection": {"key": "AZURE_AI_SEARCH_KEY"}}
        else:
            ai_search_connection = get_connection_by_id_v2(ai_search_connection_id)
            if isinstance(ai_search_connection, dict):
                endpoint = ai_search_connection["properties"]["target"]
                ai_search_args = {
                    **ai_search_args,
                    **{
                        "endpoint": ai_search_connection["properties"]["target"],
                        "api_version": ai_search_connection["properties"]
                        .get("metadata", {})
                        .get("apiVersion", AZURE_AI_SEARCH_API_VERSION),
                    },
                }
            elif ai_search_connection.target:
                api_version = AZURE_AI_SEARCH_API_VERSION
                endpoint = ai_search_connection.target
                if ai_search_connection.tags and "ApiVersion" in ai_search_connection.tags:
                    api_version = ai_search_connection.tags["ApiVersion"]
                ai_search_args = {
                    **ai_search_args,
                    **{
                        "endpoint": ai_search_connection.target,
                        "api_version": api_version
                    },
                }
            else:
                raise ValueError("Cannot get target from ai search connection")
            connection_args = {
                "connection_type": "workspace_connection",
                "connection": {"id": ai_search_connection_id},
                "endpoint": endpoint,
            }

        print("Start creating index from embeddings.")
        create_index_from_raw_embeddings(
            emb=embedder,
            acs_config=ai_search_args,
            connection=connection_args,
            output_path=save_path,
        )
    print(f"Successfully created index at {save_path}")
    return save_path


def _create_mlindex_from_existing_ai_search(
    name: str,
    embedding_model_uri: Optional[str],
    connection_id: Optional[str],
    is_serverless_connection: bool,
    ai_search_config: AzureAISearchSource,
) -> str:
    try:
        from azureml.rag.embeddings import EmbeddingsContainer
        from azureml.rag.utils.connections import get_connection_by_id_v2
    except ImportError as e:
        print(
            "In order to use build_index to build an Index locally, you must have azureml.rag installed"
        )
        raise e
    mlindex_config = {}
    connection_info = {}
    if not ai_search_config.ai_search_connection_id:
        import os

        connection_info = {
            "endpoint": os.getenv("AZURE_AI_SEARCH_ENDPOINT")
            if "AZURE_AI_SEARCH_ENDPOINT" in os.environ
            else os.getenv("AZURE_COGNITIVE_SEARCH_TARGET"),
            "connection_type": "environment",
            "connection": {"key": "AZURE_AI_SEARCH_KEY"},
        }
    else:
        ai_search_connection = get_connection_by_id_v2(ai_search_config.ai_search_connection_id)
        if isinstance(ai_search_connection, dict):
            endpoint = ai_search_connection["properties"]["target"]
        elif ai_search_connection.target:
            endpoint = ai_search_connection.target
        else:
            raise ValueError("Cannot get target from ai search connection")
        connection_info = {
            "endpoint": endpoint,
            "connection_type": "workspace_connection",
            "connection": {
                "id": ai_search_config.ai_search_connection_id,
            },
        }
    mlindex_config["index"] = {
        "kind": "acs",
        "engine": "azure-sdk",
        "index": ai_search_config.ai_search_index_name,
        "api_version": AZURE_AI_SEARCH_API_VERSION,
        "field_mapping": {
            "content": ai_search_config.ai_search_content_key,
            "embedding": ai_search_config.ai_search_embedding_key,
        },
        **connection_info,
    }

    if ai_search_config.ai_search_title_key:
        mlindex_config["index"]["field_mapping"]["title"] = ai_search_config.ai_search_title_key
    if ai_search_config.ai_search_metadata_key:
        mlindex_config["index"]["field_mapping"]["metadata"] = ai_search_config.ai_search_metadata_key

    model_connection_args: Dict[str, Optional[Union[str, Dict]]]
    if is_serverless_connection:
        connection_args = {
            "connection_type": "workspace_connection",
            "connection": {"id": connection_id},
        }
        embedding = EmbeddingsContainer.from_uri(None, credential=None, **connection_args)
    else:
        if not connection_id:
            import openai

            model_connection_args = {
                "key": openai.api_key,
            }
        else:
            model_connection_args = {"connection_type": "workspace_connection", "connection": {"id": connection_id}}
        embedding = EmbeddingsContainer.from_uri(embedding_model_uri, credential=None, **model_connection_args)
    mlindex_config["embeddings"] = embedding.get_metadata()

    path = Path.cwd() / f"{name}-mlindex"

    path.mkdir(exist_ok=True)
    with open(path / "MLIndex", "w", encoding="utf-8") as f:
        yaml.dump(mlindex_config, f)

    print(f"Successfully created index at {path}")
    return path
