import argparse
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

parser = argparse.ArgumentParser()
parser.add_argument("--documents_folder", type=str)
parser.add_argument("--chunk_size", type=int)
parser.add_argument("--document_node_output", type=str)


args = parser.parse_args()

print("documents_folder path: %s" % args.documents_folder)
print(f"chunk_size: {type(args.chunk_size)}: {args.chunk_size}")
print("document_node_output path: %s" % args.document_node_output)

print("files in input path: ")
arr = os.listdir(args.documents_folder)
print(arr)

for filename in arr:
    print("reading file: %s ..." % filename)
    with open(os.path.join(args.documents_folder, filename), "r") as handle:
        print(handle.read())

# load docs
documents = SimpleDirectoryReader(args.documents_folder).load_data()
# Convert documents into nodes
node_parser = SimpleNodeParser.from_defaults(chunk_size=args.chunk_size, chunk_overlap=0, include_metadata=True)
documents = t.cast(t.List[LlamaindexDocument], documents)
document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=documents)

jsonl_str = ""
for doc in document_nodes:
    json_dict = {"document_node": doc.to_json()}
    jsonl_str += json.dumps(json_dict) + "\n"


cur_time_str = datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
with open(os.path.join(args.document_node_output, "file-" + cur_time_str + ".jsonl"), "wt") as text_file:
    print(f"{jsonl_str}", file=text_file)
