from promptflow_test.utils import convert_request_to_raw
import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from promptflow.contracts.run_mode import RunMode  # noqa: E402


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=str, default="batch_request_e2e.json")
    parser.add_argument('--run_mode', type=lambda color: RunMode[color], choices=list(RunMode), default=RunMode.Flow)
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()
    request_file = Path(__file__).parent / args.request
    with open(request_file, "r") as f:
        request = json.load(f)
    raw_request = convert_request_to_raw(request, run_mode=args.run_mode)
    if args.output is None:
        args.output = request_file.with_suffix(".raw.json")
    else:
        args.output = request_file.parent / args.output
    with open(args.output, "w") as f:
        json.dump(raw_request, f, indent=2)
