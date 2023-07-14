import csv
import sys
import json


def transfer(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        with open(output_path, "w", encoding="utf-8") as output_f:
            for row_dict in reader:
                json.dump(row_dict, output_f)
                output_f.write("\n")

if __name__ == "__main__":
    _, _input, _output = sys.argv
    transfer(_input, _output)
