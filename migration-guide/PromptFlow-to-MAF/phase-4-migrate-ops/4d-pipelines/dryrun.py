"""
Local dry-run for the MAF Linear Flow PRS sample. Skips AML and runs the
PRS init / run / shutdown contract in-process using the sample input file.

Run from this folder:

    python dryrun.py

Requires FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL in the environment so
that 01_linear_flow.py can construct its FoundryChatClient.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))
sys.argv = [
    "entry",
    "--maf_workflow_file",
    "phase-2-rebuild/01_linear_flow.py",
]

from entry import init, run, shutdown  # noqa: E402

init()
try:
    df = pd.read_json(HERE / "data" / "sample.jsonl", lines=True)
    ctx = SimpleNamespace(minibatch_index=0, global_row_index_lower_bound=0)
    for line in run(df, ctx):
        print(line)
finally:
    shutdown()
