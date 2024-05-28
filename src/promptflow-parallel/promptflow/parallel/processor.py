# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import sys
from abc import ABC, abstractmethod
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path
from typing import List, Optional


class ParallelRunProcessor(ABC):
    @abstractmethod
    def init(self):
        raise NotImplementedError

    @abstractmethod
    def process(self, mini_batch: List[dict], context) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def finalize(self):
        raise NotImplementedError


def create_processor(working_dir: Path, args: Optional[List[str]] = None) -> ParallelRunProcessor:
    args = args or sys.argv[1:]
    parser = ArgumentParser(description="Prompt Flow Parallel Run Config")
    parser.add_argument("--amlbi_pf_run_mode", dest="pf_run_mode", required=False, type=_Mode, default=_Mode.component)
    parsed, _ = parser.parse_known_args(args)

    if parsed.pf_run_mode == _Mode.bulk:
        from promptflow.parallel._processor.bulk_processor import BulkRunProcessor

        return BulkRunProcessor(working_dir, args)
    else:
        from promptflow.parallel._processor.component_processor import ComponentRunProcessor

        return ComponentRunProcessor(working_dir, args)


class _Mode(str, Enum):
    bulk = "bulk"
    component = "component"
