from dataclasses import asdict
from enum import Enum
from typing import Union

import openai

from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow._internal import tool
from promptflow.tools.common import handle_openai_error
from promptflow.tools.exception import InvalidConnectionType


class EmbeddingModel(str, Enum):
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_SEARCH_ADA_DOC_001 = "text-search-ada-doc-001"
    TEXT_SEARCH_ADA_QUERY_001 = "text-search-ada-query-001"


@tool
@handle_openai_error()
def embedding(connection: Union[AzureOpenAIConnection, OpenAIConnection], input: str, deployment_name: str = "",
              model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_ADA_002):
    connection_dict = asdict(connection)
    if isinstance(connection, AzureOpenAIConnection):
        return openai.Embedding.create(
            input=input,
            engine=deployment_name,
            headers={"ms-azure-ai-promptflow-called-from": "aoai-tool"},
            **connection_dict,
        )["data"][0]["embedding"]
    elif isinstance(connection, OpenAIConnection):
        return openai.Embedding.create(
            input=input,
            model=model,
            **connection_dict,
        )["data"][0]["embedding"]
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for embedding api. " \
                        f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]"
        raise InvalidConnectionType(message=error_message)
