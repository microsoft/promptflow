import json
import os
import typing as t
from pathlib import Path

from constants import DOCUMENT_NODE, TEXT_CHUNK

try:
    from llama_index import SimpleDirectoryReader
    from llama_index.node_parser import SentenceSplitter
    from llama_index.readers.schema import Document as LlamaindexDocument
    from llama_index.schema import BaseNode
except ImportError:
    raise ImportError(
        "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
    )


def split_document(chunk_size, documents_folder, document_node_output):
    # load docs
    documents = SimpleDirectoryReader(
        documents_folder, recursive=True, exclude=["index.md", "README.md"], encoding="utf-8"
    ).load_data()
    # Convert documents into nodes
    node_parser = SentenceSplitter.from_defaults(chunk_size=chunk_size, chunk_overlap=0, include_metadata=True)
    documents = t.cast(t.List[LlamaindexDocument], documents)
    document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=documents)

    with open(os.path.join(document_node_output, "document_nodes.jsonl"), "wt") as text_file:
        for doc in document_nodes:
            print(json.dumps({TEXT_CHUNK: doc.text, DOCUMENT_NODE: doc.to_json()}), file=text_file)

    return str((Path(document_node_output) / "document_nodes.jsonl"))


def clean_data_and_save(test_data_set: list, test_data_output_path: str):
    cleaned_data = [
        test_data
        for test_data in test_data_set
        if (test_data and all(val for key, val in test_data.items() if key.lower() != "line_number"))
    ]

    jsonl_str = "\n".join(map(json.dumps, cleaned_data))
    with open(test_data_output_path, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)


NNNN = {

}

