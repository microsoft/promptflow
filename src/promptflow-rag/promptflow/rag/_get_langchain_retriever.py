# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from azureml.rag.mlindex import MLIndex
from promptflow.rag.constants._common import STORAGE_URI_TO_MLINDEX_PATH_FORMAT
import re
import yaml


def get_langchain_retriever_from_index(path: str):
    if re.match(STORAGE_URI_TO_MLINDEX_PATH_FORMAT, path):
        return MLIndex(path).as_langchain_retriever()

    # local path
    mlindex_path = str(Path(path) / "MLIndex") if not path.endswith("MLIndex") else path
    with open(mlindex_path, "r") as f:
        config = yaml.safe_load(f)
        return MLIndex(mlindex_config=config).as_langchain_retriever()
