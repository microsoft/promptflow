import argparse
import json
import os
import sys
import typing as t

from llama_index import SimpleDirectoryReader
from llama_index.readers import BeautifulSoupWebReader

try:
    from llama_index.node_parser import SentenceSplitter
    from llama_index.readers.schema import Document as LlamaindexDocument
    from llama_index.schema import BaseNode
except ImportError:
    raise ImportError(
        "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
    )

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from contants import DOCUMENT_NODE, TEXT_CHUNK  # noqa: E402


def split_doc(documents_folder: str, output_file_path: str, chunk_size: int, urls: list = None):
    # load docs
    if urls:
        documents = BeautifulSoupWebReader().load_data(urls=urls)
    else:
        documents = SimpleDirectoryReader(
            documents_folder, recursive=True, exclude=["index.md", "README.md"], encoding="utf-8"
        ).load_data()

    # Convert documents into nodes
    node_parser = SentenceSplitter.from_defaults(chunk_size=chunk_size, chunk_overlap=0, include_metadata=True)
    documents = t.cast(t.List[LlamaindexDocument], documents)
    document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=documents)

    jsonl_str = ""
    for doc in document_nodes:
        json_dict = {TEXT_CHUNK: doc.text, DOCUMENT_NODE: doc.to_json()}
        jsonl_str += json.dumps(json_dict) + "\n"

    with open(output_file_path, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents_folder", type=str, required=True)
    parser.add_argument("--chunk_size", type=int, required=False, default=1024)
    parser.add_argument("--document_node_output", type=str, required=True)
    args = parser.parse_args()

    print(f"documents_folder path: {args.documents_folder}")
    print(f"chunk_size: {type(args.chunk_size)}: {args.chunk_size}")
    print(f"document_node_output path: {args.document_node_output}")

    split_doc(args.documents_folder, args.document_node_output, args.chunk_size)
