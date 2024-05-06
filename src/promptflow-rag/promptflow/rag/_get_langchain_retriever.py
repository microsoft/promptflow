# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from azureml.rag.mlindex import MLIndex
from promptflow.rag.constants._common import STORAGE_URI_TO_MLINDEX_PATH_FORMAT
import re


def get_langchain_retriever_from_index(path: str):
    if not re.match(STORAGE_URI_TO_MLINDEX_PATH_FORMAT, path):
        raise ValueError(
            "Path to MLIndex file doesn't have the correct format."
        )
    return MLIndex(path).as_langchain_retriever()
