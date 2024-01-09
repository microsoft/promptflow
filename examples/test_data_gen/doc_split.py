import json
import os
import typing as t
from datetime import datetime

from llama_index import SimpleDirectoryReader

try:
    from llama_index.node_parser import SimpleNodeParser
    from llama_index.readers.schema import Document as LlamaindexDocument
    from llama_index.schema import BaseNode
except ImportError:
    raise ImportError(
        "llama_index must be installed to use this function. " "Please, install it with `pip install llama_index`."
    )


def split_doc(input_file_path: str, output_file_path: str, chunk_size: int):
    # load docs
    documents = SimpleDirectoryReader(input_file_path).load_data()
    # Convert documents into nodes
    node_parser = SimpleNodeParser.from_defaults(chunk_size=chunk_size, chunk_overlap=0, include_metadata=True)
    documents = t.cast(t.List[LlamaindexDocument], documents)
    document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=documents)

    jsonl_str = ""
    for doc in document_nodes:
        json_dict = {"document_node": doc.to_json()}
        jsonl_str += json.dumps(json_dict) + "\n"

    cur_time_str = datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
    with open(os.path.join(output_file_path, "file-" + cur_time_str + ".jsonl"), "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)
