import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input-path", type=str, required=True)
parser.add_argument("--output-path", type=str, required=True)
parser.add_argument("--count", type=int, required=True)
args = parser.parse_args()

env_var = os.environ.get("CONNECTION_KEY")
assert env_var is not None, "Environment variable CONNECTION_KEY not set!"
assert env_var != "${azure_open_ai_connection.api_key}", "Environment variable CONNECTION_KEY not resolved!"

with open(args.input_path, "r", encoding="utf-8") as f:
    input_lines = f.readlines()

assert args.count == len(input_lines), \
    f"Data number {args.count} different from input lines {len(input_lines)} in file!"

output_path = Path(args.output_path)
assert output_path.exists(), f"Output path {args.output_path!r} not exists!"
with open(output_path / "data.jsonl", "w", encoding="utf-8") as f:
    f.writelines(input_lines)
