from promptflow_test.utils import execute, assert_success
import argparse
import json
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from promptflow.contracts.run_mode import RunMode  # noqa: E402


logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch_request', type=str, required=True)
    parser.add_argument('--raise_ex', action='store_true')
    parser.add_argument('--validate_run_result', action='store_true')
    parser.add_argument('--run_mode', type=lambda color: RunMode[color], choices=list(RunMode), default=RunMode.Flow)

    args = parser.parse_args()
    output_dir = Path(__file__).parent / 'outputs'
    os.makedirs(output_dir, exist_ok=True)
    input_file = Path(args.batch_request)
    output_file = output_dir / input_file.name

    result = execute(input_file, args.run_mode, args.raise_ex)

    print(f"Result file: {output_file}")

    with open(output_file, 'w') as fout:
        json.dump(result, fout, indent=2)

    if args.validate_run_result:
        assert_success(result)
        print("Execution result validated.")
