import os
import re
from typing import Dict

from promptflow._utils.load_data import load_data
from promptflow.executor.flow_executor import FlowExecutor

IMAGE_PATH_PATTERN = r"^data:image/.*:path$"


class BatchEngine:
    def __init__(self, flow_executor: FlowExecutor):
        self.flow_executor = flow_executor

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: str,
        run_id: str = None,
    ):
        # 1. load data
        input_dicts = self._resolve_data(input_dirs)
        # 2. apply inputs mapping
        mapped_inputs = self.flow_executor.validate_and_apply_inputs_mapping(input_dicts, inputs_mapping)
        # 3. execute batch run
        batch_result = self.flow_executor.exec_bulk(mapped_inputs, run_id)
        return batch_result

    def _resolve_data(self, input_dirs: Dict[str, str]):
        result = {}
        for input_key, local_file in input_dirs.items():
            file_data = load_data(local_file)
            for each_line in file_data:
                self._resolve_image_path(local_file, each_line)
            result[input_key] = file_data
        return result

    def _resolve_image_path(self, input_dir: str, one_line_data: dict):
        for value in one_line_data.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._resolve_image(input_dir, item)
            elif isinstance(value, dict):
                self._resolve_image(input_dir, item)

    def _resolve_image(self, input_dir: str, data_dict: dict):
        input_absolute_dir = os.path.abspath(input_dir)
        for key, value in data_dict.items():
            if re.match(IMAGE_PATH_PATTERN, key):
                value = os.path.join(input_absolute_dir, value)
