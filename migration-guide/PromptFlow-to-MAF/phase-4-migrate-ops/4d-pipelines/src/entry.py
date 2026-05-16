"""
Azure ML Parallel Run Step (PRS) entry script for the
`phase-2-rebuild/01_linear_flow.py` MAF workflow.

PRS calls three top-level functions on this module per worker process:

    init()                         -- once at boot
    run(mini_batch, context)       -- once per mini-batch; returns list[str]
    shutdown()                     -- once before the worker exits

Keep this file thin. All real logic lives in `maf_prs/`.
"""
import sys
from pathlib import Path

# `code: ../..` in component.yaml uploads the migration-guide root, so the
# entry script ends up at <root>/phase-4-migrate-ops/4d-pipelines/src/entry.py.
# Prepend this directory so `import maf_prs.*` resolves cleanly regardless of
# how PRS happens to load the entry module.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from maf_prs.processor import create_processor  # noqa: E402

# Migration-guide root: <root>/phase-4-migrate-ops/4d-pipelines/src/entry.py
#                       ^^^^                                                    parents[3]
_GUIDE_ROOT = Path(__file__).resolve().parents[3]

_processor = None


def init():
    """Called once per worker process at boot."""
    global _processor
    _processor = create_processor(_GUIDE_ROOT)
    _processor.init()


def run(mini_batch, context):
    """Called once per mini-batch. Returns one JSON string per input row."""
    return _processor.process(mini_batch, context)


def shutdown():
    """Called once before the worker exits. Flushes tracing and closes the loop."""
    if _processor is not None:
        _processor.finalize()
