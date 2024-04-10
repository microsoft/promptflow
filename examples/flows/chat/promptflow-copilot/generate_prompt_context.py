# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""File for context getting tool."""
from typing import List
from promptflow.core import tool
from promptflow_vectordb.core.contracts import SearchResultEntity
import re


@tool
def generate_prompt_context(search_result: List[dict]) -> str:
    """Generate the context for the prompt."""
    def format_doc(doc: dict):
        """Format Doc."""
        return f"Content: {doc['Content']}\nSource: {doc['Source']}"

    SOURCE_KEY = "source"
    URL_KEY = "url"

    pattern = r".+/community/"
    replacement_text = "https://github.com/microsoft/promptflow/blob/main/docs/"

    retrieved_docs = []
    for item in search_result:

        entity = SearchResultEntity.from_dict(item)
        content = entity.text or ""

        source = ""
        if entity.metadata is not None:
            if SOURCE_KEY in entity.metadata:
                if URL_KEY in entity.metadata[SOURCE_KEY]:
                    source = entity.metadata[SOURCE_KEY][URL_KEY] or ""

        source = re.sub(pattern, replacement_text, source)
        retrieved_docs.append({
            "Content": content,
            "Source": source
        })
    doc_string = "\n\n".join([format_doc(doc) for doc in retrieved_docs])
    return doc_string
