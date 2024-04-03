import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input-path", type=str, required=True)
parser.add_argument("--output-path", type=str, required=True)
args = parser.parse_args()


with open(args.input_path, "r", encoding="utf-8") as f:
    input_lines = f.readlines()

output_path = Path(args.output_path)
with open(output_path / "data.jsonl", "w", encoding="utf-8") as f:
    f.writelines(input_lines)
