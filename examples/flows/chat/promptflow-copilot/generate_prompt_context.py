# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""File for context getting tool."""
from typing import List
from promptflow import tool
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

        metadata = item.get("metadata", None)
        content = item.get("text", "")

        source = ""
        if metadata is not None:
            if SOURCE_KEY in metadata:
                if URL_KEY in metadata[SOURCE_KEY]:
                    source = metadata[SOURCE_KEY][URL_KEY] or ""

            source = re.sub(pattern, replacement_text, source)

        retrieved_docs.append({
            "Content": content,
            "Source": source
        })
    doc_string = "\n\n".join([format_doc(doc) for doc in retrieved_docs])
    return doc_string
