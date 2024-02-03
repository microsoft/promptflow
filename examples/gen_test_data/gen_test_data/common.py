import json
import shutil
import typing as t
from pathlib import Path

import yaml
from constants import DOCUMENT_NODE, TEXT_CHUNK

from promptflow._utils.logger_utils import get_logger


def split_document(chunk_size, documents_folder, document_node_output):
    try:
        from llama_index import SimpleDirectoryReader
        from llama_index.node_parser import SentenceSplitter
        from llama_index.readers.schema import Document as LlamaindexDocument
        from llama_index.schema import BaseNode
    except ImportError:
        raise ImportError(
            "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
        )

    logger = get_logger("doc.split")
    logger.info("Step 1: Start to split documents to document nodes...")
    # count the number of files in documents_folder, including subfolders, use pathlib
    num_files = sum(1 for _ in Path(documents_folder).rglob("*") if _.is_file())
    logger.info(
        f"Found {num_files} files in the documents folder '{documents_folder}'. Using chunk size: {chunk_size} to split.")
    # `SimpleDirectoryReader` by default chunk the documents based on heading tags and paragraphs,
    # which may lead to small chunks.
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


def copy_flow_folder_and_set_node_inputs(flow_folder, node_inputs_override):
    logger = get_logger("data.override")
    logger.info("Overriding the values of node inputs in flag.dag.yaml...")
    if not (Path(flow_folder) / "flow.dag.yaml").is_file():
        raise ValueError(f"The file 'flag.dag.yaml' does not exist in {flow_folder}.")

    copied_folder = flow_folder + "_copy_23874934"
    if Path(copied_folder).exists():
        shutil.rmtree(copied_folder)
    shutil.copytree(flow_folder, copied_folder)

    with open(Path(copied_folder) / "flow.dag.yaml", 'r') as file:
        data = yaml.safe_load(file)

    # Update the YAML data according to the config dict
    for node_name, inputs in node_inputs_override.items():
        node = next((node for node in data['nodes'] if node['name'] == node_name), None)
        if node is None:
            shutil.rmtree(copied_folder)
            raise ValueError(f"Node '{node_name}' not found in the flag.dag.yaml.")
        for input_name in inputs:
            if input_name not in node['inputs']:
                shutil.rmtree(copied_folder)
                raise ValueError(f"Input '{input_name}' not found in node '{node_name}'.")

        node['inputs'].update(inputs)

    with open(Path(copied_folder) / "flow.dag.yaml", 'w') as file:
        yaml.dump(data, file)

    logger.info("Copied a new flow folder and overridden node inputs...")
    return copied_folder
