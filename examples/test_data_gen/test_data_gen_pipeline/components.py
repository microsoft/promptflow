import json
import os
import typing as t
from pathlib import Path

from constants import DOCUMENT_NODE, TEXT_CHUNK
from mldesigner import Input, Output, command_component

try:
    from llama_index import SimpleDirectoryReader
    from llama_index.node_parser import SentenceSplitter
    from llama_index.readers.schema import Document as LlamaindexDocument
    from llama_index.schema import BaseNode
except ImportError:
    raise ImportError(
        "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
    )


@command_component(
    name="document_split",
    version="1",
    display_name="Split documents",
    description="Split documents into chunks.",
    environment=dict(
        conda_file=Path(__file__).parent / "conda.yml",
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
    ),
)
def document_split(
    documents_folder: Input(type="uri_folder"), chunk_size: int, document_node_output: Output(type="uri_folder")
) -> str:
    """Split documents into chunks.

    Args:
        documents_folder: The folder containing documents to be split.
        chunk_size: The size of each chunk.

    Returns:
        The folder containing the split documents.
    """
    print("files in input path: ")
    arr = os.listdir(documents_folder)
    print(arr)

    # load docs
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

    with open(os.path.join(document_node_output, "document_nodes.jsonl"), "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    return str((Path(document_node_output) / "document_nodes.jsonl"))


@command_component(
    name="clean_test_data_set",
    version="1",
    display_name="Clean dataset",
    description="Clean test data set to remove empty lines.",
    environment=dict(
        conda_file=Path(__file__).parent / "conda.yml",
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
    ),
)
def clean_test_data_set(
    test_data_set_folder: Input(type="uri_folder"), test_data_output: Output(type="uri_folder")
) -> str:
    test_data_set_path = Path(test_data_set_folder) / "parallel_run_step.jsonl"
    print("test_data_file path: %s" % test_data_set_path)

    print("reading file: %s ..." % test_data_set_path)
    with open(test_data_set_path, "r") as f:
        data = [json.loads(line) for line in f]

    # Filter out empty dictionaries
    # TODO: error handling
    filtered_data = [
        {"question": d["question"], "ground_truth": d["ground_truth"], "debug_info": d["debug_info"]}
        for d in data
        if d and all(val for val in d.values())
    ]

    jsonl_str = ""
    for d in filtered_data:
        jsonl_str += json.dumps(d) + "\n"

    with open(os.path.join(test_data_output, "test_data_set.jsonl"), "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    return str((Path(test_data_output) / "test_data_set.jsonl"))
