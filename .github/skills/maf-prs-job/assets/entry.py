"""
Azure ML Parallel Run Step (PRS) entry script for a Microsoft Agent Framework
(MAF) workflow.

This file is the MAF equivalent of what `load_component(flow.dag.yaml)`
auto-generated for Prompt Flow PRS jobs.  PRS calls three top-level functions
on this module per worker process:

    init()                         -- once at boot
    run(mini_batch, context)       -- once per mini-batch; returns list[str]
    shutdown()                     -- once before the worker exits

Keep this file thin.  All real logic lives in `maf_prs/` so that adding new
modes (e.g. bulk run, aggregation) does not require touching the PRS contract.

To customise row -> workflow input mapping, edit
`maf_prs/executor.py::MafWorkflowExecutor.build_workflow_input`.
"""
import sys
from pathlib import Path

# `code: ./` in component.yaml uploads the project root, so PRS's sys.path
# only contains the project root — `maf_prs` then resolves as
# `src.maf_prs`, not `maf_prs`, and the import below would fail with
# "No module named 'maf_prs'".  Prepending this directory (`src/`) makes
# the imports work regardless of how PRS happens to load the entry module
# (`entry`, `src.entry`, …).  See gotchas.md #13.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from maf_prs.processor import create_processor  # noqa: E402

_processor = None


def init():
    """Called once per worker process at boot."""
    global _processor
    # `Path(__file__).resolve().parents[1]` is the project root that contains
    # `workflow.py` (with `create_workflow()`).  component.yaml uses
    # `code: ./` and `entry_script: src/entry.py`, so this layout puts the
    # workflow on sys.path both locally and on AML.
    _processor = create_processor(Path(__file__).resolve().parents[1])
    _processor.init()


def run(mini_batch, context):
    """Called once per mini-batch.  Returns one JSON string per input row."""
    return _processor.process(mini_batch, context)


def shutdown():
    """Called once before the worker exits.  Flushes tracing and closes the loop."""
    if _processor is not None:
        _processor.finalize()
