"""Quick smoke-test for the gen-docstring MAF workflow.

Usage:
    python test_gen_docstring.py                       # uses ./divider.py
    python test_gen_docstring.py --source path/to/file.py
"""

import argparse
import asyncio
from pathlib import Path

from workflow import create_workflow


async def main(source: str) -> None:
    wf = create_workflow()
    result = await wf.run(source)
    output = result.get_outputs()[0]
    print("=== Generated code with docstrings ===")
    print(output)


if __name__ == "__main__":
    current_folder = Path(__file__).absolute().parent
    parser = argparse.ArgumentParser(description="Generate docstrings for a Python file.")
    parser.add_argument(
        "--source",
        help="Path to the Python source file",
        default=str(current_folder / "divider.py"),
    )
    args = parser.parse_args()
    asyncio.run(main(args.source))
