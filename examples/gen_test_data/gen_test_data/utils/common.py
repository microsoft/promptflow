import json
import typing as t
from pathlib import Path

from constants import DOCUMENT_NODE, TEXT_CHUNK
from promptflow._utils.logger_utils import get_logger

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
    logger = get_logger("doc.split")
    logger.info("Step 1: Start to split documents to document nodes...")
    # count the number of files in documents_folder, including subfolders, use pathlib
    num_files = sum(1 for _ in Path(documents_folder).rglob("*") if _.is_file())
    logger.info(f"Found {num_files} files in the documents folder '{documents_folder}'. Using chunk size: {chunk_size} to split.")
    # `SimpleDirectoryReader` by default chunk the documents based on heading tags and paragraphs, which may lead to small chunks.
    # TODO: improve on top of `SimpleDirectoryReader` with a better chunking algorithm.
    chunks = SimpleDirectoryReader(documents_folder, recursive=True, encoding="utf-8").load_data()
    # Convert documents into nodes
    node_parser = SentenceSplitter.from_defaults(chunk_size=chunk_size, chunk_overlap=0, include_metadata=True)
    chunks = t.cast(t.List[LlamaindexDocument], chunks)
    document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=chunks)
    logger.info(f"Split the documents and created {len(document_nodes)} document nodes.")
    document_nodes_output_path = document_node_output / Path("document_nodes.jsonl")
    with open(document_nodes_output_path, "wt") as text_file:
        for doc in document_nodes:
            print(json.dumps({TEXT_CHUNK: doc.text, DOCUMENT_NODE: doc.to_json()}), file=text_file)

    logger.info(f"Saved document nodes to '{document_nodes_output_path}'.")
    return str((Path(document_node_output) / "document_nodes.jsonl"))


def clean_data_and_save(test_data_set: list, test_data_output_path: str):
    logger = get_logger("data.clean")
    logger.info("Step 3: Start to clean invalid test data...")
    logger.info(f"Collected {len(test_data_set)} test data after the batch run.")
    cleaned_data = []

    for test_data in test_data_set:
        if test_data and all(
                val and val != "(Failed)" for key, val in test_data.items() if key.lower() != "line_number"
        ):
            cleaned_data.append(test_data)

    jsonl_str = "\n".join(map(json.dumps, cleaned_data))
    with open(test_data_output_path, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    # log debug info path.
    logger.info(f"Removed {len(test_data_set) - len(cleaned_data)} invalid test data.")
    logger.info(f"Saved {len(cleaned_data)} valid test data to {test_data_output_path}.")


def count_non_blank_lines(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    non_blank_lines = len([line for line in lines if line.strip()])
    return non_blank_lines