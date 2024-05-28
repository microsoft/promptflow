# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


def output_file_pattern(suffix: str) -> str:
    return f"temp_*_*_{suffix}"


@dataclass
class ParallelRunConfig:
    pf_model_dir: Optional[Path] = None
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    output_file_pattern: str = output_file_pattern("parallel_run_step.jsonl")
    input_mapping: Dict[str, str] = field(default_factory=dict)
    side_input_dir: Optional[Path] = None  # side input to apply input mapping with
    connections_override: Optional[Dict[str, str]] = None
    debug_output_dir: Optional[Path] = None
    logging_level: str = "INFO"

    @property
    def is_debug_enabled(self):
        return self.logging_level.upper() == "DEBUG" and self.debug_output_dir is not None
