import fnmatch
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "-g",
    "--input-glob",
    help="Input glob patterns for matching.",
)
parser.add_argument(
    "-f",
    "--input-file",
    help="Input file name.",
)
args = parser.parse_args()
print(fnmatch.fnmatch(args.input_file, args.input_glob))
