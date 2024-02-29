# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import signal
from typing import Dict

import psutil

from promptflow._utils.logger_utils import service_logger


class ProcessManager:
    _instance = None
    _processes_mapping: Dict[str, int]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ProcessManager, cls).__new__(cls)
            cls._instance._processes_mapping = {}
        return cls._instance

    def start_process(self, run_id: str, process_id: int):
        self._processes_mapping[run_id] = process_id

    def get_process(self, run_id: str):
        return self._processes_mapping.get(run_id, None)

    def remove_process(self, run_id: str):
        self._processes_mapping.pop(run_id, None)

    def end_process(self, run_id: str):
        process_id = self._processes_mapping.pop(run_id, None)
        if process_id:
            try:
                process = psutil.Process(process_id)
                if process.is_running():
                    process.send_signal(signal.SIGINT)
                    service_logger.info(f"Kill process[{process.pid}] for run[{run_id}] with SIGINT.")
                    # wait for 30s for executor process to gracefully shutdown
                    process.wait(timeout=30)
                    service_logger.info(f"Successfully terminated process[{process.pid}] for run[{run_id}].")
                else:
                    service_logger.info(f"Process[{process.pid}] for run[{run_id}] is already terminated.")
            except psutil.TimeoutExpired:
                if process.is_running():
                    # force kill if still alive
                    process.send_signal(signal.SIGKILL)
                    service_logger.info(f"Kill process[{process.pid}] for run[{run_id}] with SIGKILL.")
            except psutil.NoSuchProcess:
                service_logger.warning(
                    f"Process[{process.pid}] for run[{run_id}] not found, it might have already terminated."
                )
        else:
            service_logger.info(f"Process for run[{run_id}] not found in mapping, it may have already been removed.")
