# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

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

    def remove_process(self, run_id: str):
        self._processes_mapping.pop(run_id, None)

    def end_process(self, run_id: str):
        process_id = self._processes_mapping.get(run_id, None)
        if process_id:
            try:
                process = psutil.Process(process_id)
                if process.is_running():
                    process.terminate()
                    process.wait()
                    service_logger.info(f"Successfully terminated process[{process.pid}] for run[{run_id}].")
                else:
                    service_logger.info(f"Process[{process.pid}] for run[{run_id}] is already terminated.")
            except psutil.NoSuchProcess:
                service_logger.warning(
                    f"Process[{process.pid}] for run[{run_id}] not found, it might have already terminated."
                )
            finally:
                self._processes_mapping.pop(run_id, None)
        else:
            service_logger.info(
                f"Process[{process_id}] for run[{run_id}] not found in mapping, it may have already been removed."
            )
