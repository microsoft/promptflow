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
parser.add_argument("--doc_split_0_input", type=str)
parser.add_argument("--doc_split_0_chunk_size", type=int)
parser.add_argument("--doc_split_0_output", type=str)


args = parser.parse_args()

print("doc_split_0_input path: %s" % args.doc_split_0_input)
print(f"doc_split_0_chunk_size: {type(args.doc_split_0_chunk_size)}: {args.doc_split_0_chunk_size}")
print("doc_split_0_output path: %s" % args.doc_split_0_output)

print("files in input path: ")
arr = os.listdir(args.doc_split_0_input)
print(arr)

for filename in arr:
    print("reading file: %s ..." % filename)
    with open(os.path.join(args.doc_split_0_input, filename), "r") as handle:
        print(handle.read())

# load docs
documents = SimpleDirectoryReader(args.doc_split_0_input).load_data()
# Convert documents into nodes
node_parser = SimpleNodeParser.from_defaults(
    chunk_size=args.doc_split_0_chunk_size, chunk_overlap=0, include_metadata=True
)
documents = t.cast(t.List[LlamaindexDocument], documents)
document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=documents)

jsonl_str = ""
for doc in document_nodes:
    json_dict = {"document_node": doc.to_json()}
    jsonl_str += json.dumps(json_dict) + "\n"


cur_time_str = datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
with open(os.path.join(args.doc_split_0_output, "file-" + cur_time_str + ".jsonl"), "wt") as text_file:
    print(f"{jsonl_str}", file=text_file)
