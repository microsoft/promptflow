# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import signal
from multiprocessing import Process
from typing import Dict

from promptflow._utils.logger_utils import service_logger


class ProcessManager:
    _instance = None
    _processes_mapping: Dict[str, Process]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ProcessManager, cls).__new__(cls)
            cls._instance._processes_mapping = {}
        return cls._instance

    def start_process(self, run_id: str, process: Process):
        self._processes_mapping[run_id] = process

    def get_process(self, run_id: str) -> Process:
        return self._processes_mapping.get(run_id, None)

    def remove_process(self, run_id: str) -> Process:
        return self._processes_mapping.pop(run_id, None)

    def end_process(self, run_id: str):
        process = self.remove_process(run_id)
        if process and process.is_alive():
            try:
                # Executor will handle SIGINT.
                os.kill(process.pid, signal.SIGINT)
                service_logger.info(f"Kill process[{process.pid}] for run[{run_id}] with SIGINT.")
                # Wait for 30s for executor process to gracefully shutdown
                process.join(timeout=30)
                if process.is_alive():
                    # Force kill if still alive
                    os.kill(process.pid, signal.SIGKILL)
                    service_logger.info(f"Kill process[{process.pid}] for run[{run_id}] with SIGKILL.")
                service_logger.info(f"Successfully terminated process[{process.pid}] for run[{run_id}].")
            except ProcessLookupError:
                service_logger.info(
                    f"Process[{process.pid}] for run[{run_id}] not found, it might have already terminated."
                )
        else:
            service_logger.info(f"Process for run[{run_id}] not found in mapping, it may have already been removed.")
